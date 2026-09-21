"""Соединение SQLite: PRAGMA WAL и жизненный цикл подключения."""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

from bot.db.sql import unicode_lower

logger = logging.getLogger(__name__)


class Database:
    """Обёртка над одним соединением aiosqlite с режимом WAL."""

    def __init__(self, path: str) -> None:
        """Создать объект БД без открытия соединения.

        Args:
            path: Путь к файлу SQLite.
        """
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Открыть соединение и включить PRAGMA. Схему создают репозитории."""
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self._path, timeout=30)
        self._conn.row_factory = aiosqlite.Row

        cursor = await self._conn.execute("PRAGMA journal_mode=WAL")
        journal_mode = await cursor.fetchone()
        await self._conn.execute("PRAGMA synchronous=FULL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.create_function(
            "unicode_lower",
            1,
            unicode_lower,
            deterministic=True,
        )
        await self._conn.commit()
        logger.info("PRAGMA journal_mode=%s", journal_mode[0] if journal_mode else "unknown")
        logger.info("База данных подключена: %s", self._path)

    async def close(self) -> None:
        """Закрыть соединение с базой, если оно открыто."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.info("Соединение с базой данных закрыто")

    def _require_conn(self) -> aiosqlite.Connection:
        """Вернуть активное соединение или выбросить ошибку."""
        if self._conn is None:
            raise RuntimeError("База данных не подключена. Вызовите connect().")
        return self._conn

    @property
    def connection(self) -> aiosqlite.Connection:
        """Активное соединение SQLite для репозиториев."""
        return self._require_conn()

    @property
    def path(self) -> str:
        """Путь к файлу базы."""
        return self._path
