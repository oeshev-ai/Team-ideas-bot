"""Запись и чтение таблицы audit_log."""

from __future__ import annotations

import logging

from bot.audit.models import AUDIT_LIMIT, DETAILS_LIMIT, AuditEntry
from bot.db.connection import Database

logger = logging.getLogger(__name__)


def clip_details(details: str | None) -> str | None:
    """Обрезать details до DETAILS_LIMIT символов."""
    if details is None:
        return None
    if len(details) <= DETAILS_LIMIT:
        return details
    return details[:DETAILS_LIMIT]


class AuditRepository:
    """Репозиторий журнала действий. Ошибка записи не пробрасывается наружу."""

    def __init__(self, db: Database) -> None:
        """Привязать журнал к уже открытому соединению БД."""
        self._db = db

    async def init_schema(self) -> None:
        """Создать таблицу audit_log и индекс, если их ещё нет."""
        conn = self._db.connection
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                action TEXT NOT NULL,
                target_id INTEGER,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_chat_created
            ON audit_log (chat_id, created_at DESC)
            """
        )
        await conn.commit()
        logger.info("Таблица audit_log инициализирована")

    async def log_action(
        self,
        chat_id: int,
        user_id: int,
        username: str | None,
        action: str,
        target_id: int | None = None,
        details: str | None = None,
    ) -> None:
        """Записать действие в журнал. Сбой записи не прерывает команду."""
        try:
            conn = self._db.connection
            cursor = await conn.execute(
                """
                INSERT INTO audit_log (
                    chat_id, user_id, username, action, target_id, details
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    user_id,
                    username,
                    action,
                    target_id,
                    clip_details(details),
                ),
            )
            await conn.commit()
            logger.info(
                "БД: вставлено строк=%s таблица=audit_log action=%s target_id=%s",
                cursor.rowcount,
                action,
                target_id,
            )
        except Exception:
            logger.exception("Не удалось записать действие в audit_log")

    async def get_recent_actions(
        self,
        chat_id: int,
        limit: int = AUDIT_LIMIT,
    ) -> list[AuditEntry]:
        """Вернуть последние записи журнала текущего чата (новые сверху)."""
        conn = self._db.connection
        cursor = await conn.execute(
            """
            SELECT id, chat_id, user_id, username, action, target_id, details, created_at
            FROM audit_log
            WHERE chat_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (chat_id, limit),
        )
        rows = await cursor.fetchall()
        entries: list[AuditEntry] = []
        for row in rows:
            target = row["target_id"]
            entries.append(
                AuditEntry(
                    id=int(row["id"]),
                    chat_id=int(row["chat_id"]),
                    user_id=int(row["user_id"]),
                    username=row["username"],
                    action=row["action"],
                    target_id=int(target) if target is not None else None,
                    details=row["details"],
                    created_at=row["created_at"],
                )
            )
        return entries

    async def get_recent_actions_for_chats(
        self,
        chat_ids: list[int],
        limit: int = AUDIT_LIMIT,
    ) -> list[AuditEntry]:
        """Последние записи журнала по нескольким чатам (новые сверху)."""
        if not chat_ids:
            return []
        conn = self._db.connection
        placeholders = ",".join("?" * len(chat_ids))
        cursor = await conn.execute(
            f"""
            SELECT id, chat_id, user_id, username, action, target_id, details, created_at
            FROM audit_log
            WHERE chat_id IN ({placeholders})
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (*chat_ids, limit),
        )
        rows = await cursor.fetchall()
        entries: list[AuditEntry] = []
        for row in rows:
            target = row["target_id"]
            entries.append(
                AuditEntry(
                    id=int(row["id"]),
                    chat_id=int(row["chat_id"]),
                    user_id=int(row["user_id"]),
                    username=row["username"],
                    action=row["action"],
                    target_id=int(target) if target is not None else None,
                    details=row["details"],
                    created_at=row["created_at"],
                )
            )
        return entries
