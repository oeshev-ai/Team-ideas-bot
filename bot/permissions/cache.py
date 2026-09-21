"""Кэш статуса администратора чата."""

from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)

ADMIN_STATUSES = frozenset({"administrator", "creator"})
CACHE_TTL_SECONDS = 60.0


class AdminCache:
    """Кэш ответов get_chat_member на CACHE_TTL_SECONDS секунд."""

    def __init__(self, ttl_seconds: float = CACHE_TTL_SECONDS) -> None:
        """Создать пустой кэш.

        Args:
            ttl_seconds: Время жизни записи в секундах.
        """
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
        self._items: dict[tuple[int, int], tuple[float, bool]] = {}

    async def is_chat_admin(self, bot: Bot, chat_id: int, user_id: int) -> bool:
        """Вернуть True, если пользователь — administrator или creator чата.

        При ошибке Telegram API пользователь считается обычным участником.
        """
        now = time.monotonic()
        key = (chat_id, user_id)

        async with self._lock:
            cached = self._items.get(key)
            if cached is not None and cached[0] > now:
                return cached[1]

        is_admin = await self._fetch_is_admin(bot, chat_id, user_id)
        expires_at = time.monotonic() + self._ttl

        async with self._lock:
            self._items[key] = (expires_at, is_admin)
        return is_admin

    async def _fetch_is_admin(self, bot: Bot, chat_id: int, user_id: int) -> bool:
        """Запросить статус участника у Telegram. Ошибка → не админ."""
        try:
            member = await bot.get_chat_member(chat_id, user_id)
        except TelegramAPIError:
            logger.warning(
                "Не удалось получить статус участника chat_id=%s user_id=%s",
                chat_id,
                user_id,
                exc_info=True,
            )
            return False
        except Exception:
            logger.exception(
                "Неожиданная ошибка при get_chat_member chat_id=%s user_id=%s",
                chat_id,
                user_id,
            )
            return False

        status = getattr(member.status, "value", member.status)
        return str(status) in ADMIN_STATUSES
