"""Команды группового чата: только /start и /add."""

from __future__ import annotations

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.handlers.add import cmd_add
from bot.handlers.common import GROUP_START_TEXT

router = Router(name="group_commands")


@router.message(CommandStart())
async def cmd_start_group(message: Message) -> None:
    """Короткое приветствие в группе: только /add."""
    await message.answer(GROUP_START_TEXT, parse_mode=ParseMode.HTML)


router.message.register(cmd_add, Command("add"))
