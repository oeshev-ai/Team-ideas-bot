"""CRUD-операции для таблицы tasks."""

from __future__ import annotations

import logging

import aiosqlite

from bot.db.connection import Database
from bot.db.models import ChatStats, Task
from bot.db.sql import TASK_COLUMNS, escape_like

logger = logging.getLogger(__name__)

LIST_LIMIT = 50


def row_to_task(row: aiosqlite.Row) -> Task:
    """Преобразовать строку SQLite в словарь задачи."""
    deleted_by = row["deleted_by"]
    return Task(
        id=int(row["id"]),
        chat_id=int(row["chat_id"]),
        user_id=int(row["user_id"]),
        username=row["username"],
        text=row["text"],
        created_at=row["created_at"],
        status=row["status"],
        deleted_at=row["deleted_at"],
        deleted_by=int(deleted_by) if deleted_by is not None else None,
    )


class TaskRepository:
    """Репозиторий задач: схема и операции чтения/записи."""

    def __init__(self, db: Database) -> None:
        """Привязать репозиторий к открытому соединению.

        Args:
            db: Слой соединения SQLite.
        """
        self._db = db

    async def init_schema(self) -> None:
        """Создать таблицу tasks, недостающие колонки и индекс."""
        conn = self._db.connection
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                status TEXT NOT NULL DEFAULT 'open',
                deleted_at TEXT,
                deleted_by INTEGER
            )
            """
        )
        await self._ensure_column("deleted_at", "TEXT")
        await self._ensure_column("deleted_by", "INTEGER")
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tasks_chat_status
            ON tasks (chat_id, status, id)
            """
        )
        await conn.commit()
        logger.info("Таблица tasks инициализирована")

    async def _ensure_column(self, name: str, sql_type: str) -> None:
        """Добавить колонку, если её нет в уже существующей таблице."""
        allowed = {"deleted_at": "TEXT", "deleted_by": "INTEGER"}
        if name not in allowed or allowed[name] != sql_type:
            raise ValueError(f"Недопустимая колонка для миграции: {name} {sql_type}")

        conn = self._db.connection
        cursor = await conn.execute("PRAGMA table_info(tasks)")
        rows = await cursor.fetchall()
        existing = {row["name"] for row in rows}
        if name not in existing:
            await conn.execute(f"ALTER TABLE tasks ADD COLUMN {name} {sql_type}")
            logger.info("Добавлена колонка %s в таблицу tasks", name)

    async def add_task(
        self,
        chat_id: int,
        user_id: int,
        username: str | None,
        text: str,
    ) -> int:
        """Добавить открытую задачу и вернуть её id."""
        conn = self._db.connection
        cursor = await conn.execute(
            """
            INSERT INTO tasks (chat_id, user_id, username, text)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, user_id, username, text),
        )
        await conn.commit()
        task_id = cursor.lastrowid
        if task_id is None:
            raise RuntimeError("Не удалось получить id созданной задачи")
        logger.info(
            "БД: вставлено строк=%s таблица=tasks id=%s chat_id=%s",
            cursor.rowcount,
            task_id,
            chat_id,
        )
        return int(task_id)

    async def get_tasks(
        self,
        chat_id: int,
        limit: int = LIST_LIMIT,
    ) -> tuple[list[Task], bool]:
        """Вернуть открытые задачи чата (новые сверху) и флаг «есть ещё»."""
        conn = self._db.connection
        cursor = await conn.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM tasks
            WHERE chat_id = ? AND status = 'open'
            ORDER BY id DESC
            LIMIT ?
            """,
            (chat_id, limit + 1),
        )
        rows = await cursor.fetchall()
        has_more = len(rows) > limit
        tasks = [row_to_task(row) for row in rows[:limit]]
        return tasks, has_more

    async def search_tasks(
        self,
        chat_id: int,
        query: str,
        limit: int = LIST_LIMIT,
    ) -> tuple[list[Task], bool]:
        """Найти открытые задачи по подстроке в тексте или username."""
        conn = self._db.connection
        pattern = escape_like(query.casefold())
        cursor = await conn.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM tasks
            WHERE chat_id = ?
              AND status = 'open'
              AND (
                    unicode_lower(text) LIKE '%' || ? || '%' ESCAPE '!'
                 OR unicode_lower(COALESCE(username, '')) LIKE '%' || ? || '%' ESCAPE '!'
              )
            ORDER BY id DESC
            LIMIT ?
            """,
            (chat_id, pattern, pattern, limit + 1),
        )
        rows = await cursor.fetchall()
        has_more = len(rows) > limit
        tasks = [row_to_task(row) for row in rows[:limit]]
        return tasks, has_more

    async def mark_done(self, chat_id: int, task_id: int) -> bool:
        """Отметить открытую задачу текущего чата выполненной."""
        conn = self._db.connection
        cursor = await conn.execute(
            """
            UPDATE tasks
            SET status = 'done'
            WHERE id = ? AND chat_id = ? AND status = 'open'
            """,
            (task_id, chat_id),
        )
        await conn.commit()
        updated = cursor.rowcount > 0
        logger.info(
            "БД: обновлено строк=%s таблица=tasks id=%s status=done chat_id=%s",
            cursor.rowcount,
            task_id,
            chat_id,
        )
        return updated

    async def get_task(self, chat_id: int, task_id: int) -> Task | None:
        """Вернуть задачу текущего чата по id или None."""
        conn = self._db.connection
        cursor = await conn.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM tasks
            WHERE id = ? AND chat_id = ?
            """,
            (task_id, chat_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return row_to_task(row)

    async def soft_delete(self, chat_id: int, task_id: int, deleted_by: int) -> bool:
        """Мягко удалить задачу текущего чата (status='deleted')."""
        conn = self._db.connection
        cursor = await conn.execute(
            """
            UPDATE tasks
            SET status = 'deleted',
                deleted_at = datetime('now'),
                deleted_by = ?
            WHERE id = ? AND chat_id = ? AND status != 'deleted'
            """,
            (deleted_by, task_id, chat_id),
        )
        await conn.commit()
        updated = cursor.rowcount > 0
        logger.info(
            "БД: обновлено строк=%s таблица=tasks id=%s status=deleted chat_id=%s",
            cursor.rowcount,
            task_id,
            chat_id,
        )
        return updated

    async def get_stats(self, chat_id: int, user_id: int) -> ChatStats:
        """Посчитать задачи чата по статусам и число задач пользователя."""
        conn = self._db.connection
        cursor = await conn.execute(
            """
            SELECT status, COUNT(*) AS cnt
            FROM tasks
            WHERE chat_id = ?
            GROUP BY status
            """,
            (chat_id,),
        )
        rows = await cursor.fetchall()
        counts = {"open": 0, "done": 0, "deleted": 0}
        for row in rows:
            status = row["status"]
            if status in counts:
                counts[status] = int(row["cnt"])

        cursor = await conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM tasks
            WHERE chat_id = ? AND user_id = ?
            """,
            (chat_id, user_id),
        )
        user_row = await cursor.fetchone()
        user_tasks = int(user_row["cnt"]) if user_row else 0

        return ChatStats(
            open=counts["open"],
            done=counts["done"],
            deleted=counts["deleted"],
            user_tasks=user_tasks,
        )

    async def get_all_tasks_for_export(self, chat_id: int) -> list[Task]:
        """Вернуть все задачи чата для экспорта (новые сверху)."""
        conn = self._db.connection
        cursor = await conn.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM tasks
            WHERE chat_id = ?
            ORDER BY id DESC
            """,
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return [row_to_task(row) for row in rows]

    async def get_distinct_chat_ids(self) -> list[int]:
        """Вернуть все chat_id, которые встречаются в таблице tasks."""
        conn = self._db.connection
        cursor = await conn.execute(
            "SELECT DISTINCT chat_id FROM tasks ORDER BY chat_id"
        )
        rows = await cursor.fetchall()
        return [int(row["chat_id"]) for row in rows]

    async def get_task_by_id(self, task_id: int) -> Task | None:
        """Вернуть задачу по id без фильтра по чату."""
        conn = self._db.connection
        cursor = await conn.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return row_to_task(row)

    async def get_tasks_for_chats(
        self,
        chat_ids: list[int],
        status: str = "open",
        limit: int = LIST_LIMIT,
    ) -> tuple[list[Task], bool]:
        """Выбрать задачи из набора чатов (новые сверху)."""
        if not chat_ids:
            return [], False
        conn = self._db.connection
        placeholders = ",".join("?" * len(chat_ids))
        cursor = await conn.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM tasks
            WHERE chat_id IN ({placeholders}) AND status = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (*chat_ids, status, limit + 1),
        )
        rows = await cursor.fetchall()
        has_more = len(rows) > limit
        return [row_to_task(row) for row in rows[:limit]], has_more

    async def search_tasks_for_chats(
        self,
        chat_ids: list[int],
        query: str,
        status: str = "open",
        limit: int = LIST_LIMIT,
    ) -> tuple[list[Task], bool]:
        """Поиск по открытым задачам сразу в нескольких чатах."""
        if not chat_ids:
            return [], False
        conn = self._db.connection
        pattern = escape_like(query.casefold())
        placeholders = ",".join("?" * len(chat_ids))
        cursor = await conn.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM tasks
            WHERE chat_id IN ({placeholders})
              AND status = ?
              AND (
                    unicode_lower(text) LIKE '%' || ? || '%' ESCAPE '!'
                 OR unicode_lower(COALESCE(username, '')) LIKE '%' || ? || '%' ESCAPE '!'
              )
            ORDER BY id DESC
            LIMIT ?
            """,
            (*chat_ids, status, pattern, pattern, limit + 1),
        )
        rows = await cursor.fetchall()
        has_more = len(rows) > limit
        return [row_to_task(row) for row in rows[:limit]], has_more

    async def get_all_tasks_for_chats(self, chat_ids: list[int]) -> list[Task]:
        """Все задачи указанных чатов для экспорта (новые сверху)."""
        if not chat_ids:
            return []
        conn = self._db.connection
        placeholders = ",".join("?" * len(chat_ids))
        cursor = await conn.execute(
            f"""
            SELECT {TASK_COLUMNS}
            FROM tasks
            WHERE chat_id IN ({placeholders})
            ORDER BY id DESC
            """,
            tuple(chat_ids),
        )
        rows = await cursor.fetchall()
        return [row_to_task(row) for row in rows]

    async def get_user_stats_for_chats(
        self,
        user_id: int,
        chat_ids: list[int],
    ) -> ChatStats:
        """Статистика по списку чатов и число задач текущего пользователя."""
        empty = ChatStats(open=0, done=0, deleted=0, user_tasks=0)
        if not chat_ids:
            return empty

        conn = self._db.connection
        placeholders = ",".join("?" * len(chat_ids))
        cursor = await conn.execute(
            f"""
            SELECT status, COUNT(*) AS cnt
            FROM tasks
            WHERE chat_id IN ({placeholders})
            GROUP BY status
            """,
            tuple(chat_ids),
        )
        rows = await cursor.fetchall()
        counts = {"open": 0, "done": 0, "deleted": 0}
        for row in rows:
            status = row["status"]
            if status in counts:
                counts[status] = int(row["cnt"])

        cursor = await conn.execute(
            f"""
            SELECT COUNT(*) AS cnt
            FROM tasks
            WHERE chat_id IN ({placeholders}) AND user_id = ?
            """,
            (*chat_ids, user_id),
        )
        user_row = await cursor.fetchone()
        user_tasks = int(user_row["cnt"]) if user_row else 0
        return ChatStats(
            open=counts["open"],
            done=counts["done"],
            deleted=counts["deleted"],
            user_tasks=user_tasks,
        )

    async def get_open_counts_by_chat(self, chat_ids: list[int]) -> dict[int, int]:
        """Количество открытых задач по каждому chat_id."""
        if not chat_ids:
            return {}
        conn = self._db.connection
        placeholders = ",".join("?" * len(chat_ids))
        cursor = await conn.execute(
            f"""
            SELECT chat_id, COUNT(*) AS cnt
            FROM tasks
            WHERE chat_id IN ({placeholders}) AND status = 'open'
            GROUP BY chat_id
            """,
            tuple(chat_ids),
        )
        rows = await cursor.fetchall()
        return {int(row["chat_id"]): int(row["cnt"]) for row in rows}
