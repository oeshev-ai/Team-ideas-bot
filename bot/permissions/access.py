"""Доступ пользователя к чатам с задачами: Telegram API и кэш."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError

from bot.db.tasks import TaskRepository

logger = logging.getLogger(__name__)

MEMBER_STATUSES = frozenset({"member", "administrator", "creator"})
ADMIN_STATUSES = frozenset({"administrator", "creator"})
ACCESS_TTL_SECONDS = 300.0
TITLE_TTL_SECONDS = 600.0
API_CONCURRENCY = 5


@dataclass(frozen=True)
class ChatAccess:
    """Доступ пользователя к одному чату с задачами."""

    chat_id: int
    status: str

    @property
    def is_admin(self) -> bool:
        """True, если пользователь администратор или создатель чата."""
        return self.status in ADMIN_STATUSES

    @property
    def role_label(self) -> str:
        """Подпись роли для /chats."""
        return "администратор" if self.is_admin else "участник"


class ChatAccessService:
    """Кэш доступных чатов (5 мин) и названий чатов (10 мин)."""

    def __init__(self) -> None:
        """Создать пустые кэши."""
        self._lock = asyncio.Lock()
        self._access: dict[int, tuple[float, list[ChatAccess]]] = {}
        self._titles: dict[int, tuple[float, str]] = {}

    async def get_accessible_chats(
        self,
        bot: Bot,
        tasks: TaskRepository,
        user_id: int,
    ) -> list[ChatAccess]:
        """Вернуть чаты, в которых пользователь member/administrator/creator.

        Группы проверяются через get_chat_member. Личные чаты других людей
        пропускаются. Свой чат с ботом включается, если в нём есть задачи.
        """
        now = time.monotonic()
        async with self._lock:
            cached = self._access.get(user_id)
            if cached is not None and cached[0] > now:
                return list(cached[1])

        chat_ids = await tasks.get_distinct_chat_ids()
        group_ids = [cid for cid in chat_ids if cid < 0]
        found = await self._probe_membership(bot, user_id, group_ids)
        if user_id in chat_ids:
            found.append(ChatAccess(chat_id=user_id, status="creator"))
        expires_at = time.monotonic() + ACCESS_TTL_SECONDS
        async with self._lock:
            self._access[user_id] = (expires_at, found)
        return list(found)

    async def get_admin_chats(
        self,
        bot: Bot,
        tasks: TaskRepository,
        user_id: int,
    ) -> list[ChatAccess]:
        """Чаты, где пользователь администратор или создатель."""
        chats = await self.get_accessible_chats(bot, tasks, user_id)
        return [item for item in chats if item.is_admin]

    async def get_chat_title(self, bot: Bot, chat_id: int) -> str:
        """Вернуть название чата с кэшем на 10 минут."""
        now = time.monotonic()
        async with self._lock:
            cached = self._titles.get(chat_id)
            if cached is not None and cached[0] > now:
                return cached[1]

        title = await self._fetch_title(bot, chat_id)
        expires_at = time.monotonic() + TITLE_TTL_SECONDS
        async with self._lock:
            self._titles[chat_id] = (expires_at, title)
        return title

    async def titles_for(
        self,
        bot: Bot,
        chat_ids: Iterable[int],
    ) -> dict[int, str]:
        """Получить названия для набора чатов."""
        result: dict[int, str] = {}
        for chat_id in chat_ids:
            result[chat_id] = await self.get_chat_title(bot, chat_id)
        return result

    async def _probe_membership(
        self,
        bot: Bot,
        user_id: int,
        chat_ids: list[int],
    ) -> list[ChatAccess]:
        """Параллельно проверить членство, не упираясь в лимиты API."""
        if not chat_ids:
            return []

        semaphore = asyncio.Semaphore(API_CONCURRENCY)

        async def check(chat_id: int) -> ChatAccess | None:
            async with semaphore:
                return await self._member_access(bot, chat_id, user_id)

        results = await asyncio.gather(*(check(chat_id) for chat_id in chat_ids))
        return [item for item in results if item is not None]

    async def _member_access(
        self,
        bot: Bot,
        chat_id: int,
        user_id: int,
    ) -> ChatAccess | None:
        """Один вызов get_chat_member. Ошибка API → чат недоступен."""
        try:
            member = await bot.get_chat_member(chat_id, user_id)
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            logger.warning(
                "Нет доступа к участнику chat_id=%s user_id=%s: %s",
                chat_id,
                user_id,
                exc,
            )
            return None
        except TelegramAPIError:
            logger.warning(
                "Ошибка Telegram при get_chat_member chat_id=%s user_id=%s",
                chat_id,
                user_id,
                exc_info=True,
            )
            return None
        except Exception:
            logger.exception(
                "Неожиданная ошибка get_chat_member chat_id=%s user_id=%s",
                chat_id,
                user_id,
            )
            return None

        status = str(getattr(member.status, "value", member.status))
        if status not in MEMBER_STATUSES:
            return None
        return ChatAccess(chat_id=chat_id, status=status)

    async def _fetch_title(self, bot: Bot, chat_id: int) -> str:
        """Запросить title чата. При ошибке вернуть строковый id."""
        try:
            chat = await bot.get_chat(chat_id)
        except TelegramAPIError:
            logger.warning("Не удалось получить чат %s", chat_id, exc_info=True)
            return str(chat_id)

        title = chat.title or getattr(chat, "full_name", None) or chat.username
        if title:
            return str(title)
        return str(chat_id)
