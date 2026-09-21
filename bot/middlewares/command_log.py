"""Логирование входящих команд в технический лог."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.filters import CommandObject
from aiogram.types import Message

logger = logging.getLogger(__name__)


class IncomingCommandMiddleware(BaseMiddleware):
    """Пишет в технический лог каждую входящую команду."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        command: CommandObject | None = data.get("command")
        if command is not None:
            user = event.from_user
            logger.info(
                "Входящая команда user_id=%s username=%s chat_id=%s "
                "команда=/%s аргументы=%s",
                user.id if user else None,
                user.username if user else None,
                event.chat.id,
                command.command,
                command.args or "",
            )
        return await handler(event, data)
