"""Команды /start и /help в личке."""

from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.db.tasks import TaskRepository
from bot.handlers.common import HELP_TEXT, PRIVATE_START_TEXT
from bot.permissions.access import ChatAccessService

logger = logging.getLogger(__name__)

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start_private(
    message: Message,
    bot: Bot,
    tasks: TaskRepository,
    access: ChatAccessService,
) -> None:
    """Приветствие в личке и прогрев кэша доступных чатов."""
    if message.from_user is not None:
        try:
            await access.get_accessible_chats(bot, tasks, message.from_user.id)
        except Exception:
            logger.exception("Не удалось прогреть кэш чатов при /start")
    await message.answer(PRIVATE_START_TEXT, parse_mode=ParseMode.HTML)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Подробная справка. Только личка (роутер с фильтром private)."""
    await message.answer(HELP_TEXT, parse_mode=ParseMode.HTML)
