"""Команда /audit в личке: журнал по чатам, где пользователь админ."""

from __future__ import annotations

import logging
from html import escape

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.audit.models import AUDIT_LIMIT
from bot.audit.repository import AuditRepository
from bot.db.tasks import TaskRepository
from bot.handlers.common import format_audit_line, send_html_parts
from bot.permissions.access import ChatAccessService

logger = logging.getLogger(__name__)

router = Router(name="audit")


@router.message(Command("audit"))
async def cmd_audit(
    message: Message,
    bot: Bot,
    tasks: TaskRepository,
    audit: AuditRepository,
    access: ChatAccessService,
) -> None:
    """Показать последние записи журнала по чатам, где пользователь админ."""
    if message.from_user is None:
        await message.answer("Не могу определить отправителя.")
        return

    try:
        admin_chats = await access.get_admin_chats(bot, tasks, message.from_user.id)
        if not admin_chats:
            await message.answer("Команда доступна только администраторам чатов.")
            return

        chat_ids = [item.chat_id for item in admin_chats]
        entries = await audit.get_recent_actions_for_chats(chat_ids, AUDIT_LIMIT)
        titles = await access.titles_for(bot, {entry["chat_id"] for entry in entries})
    except Exception:
        logger.exception("Ошибка при чтении журнала действий")
        await message.answer("Не удалось получить журнал. Попробуйте ещё раз.")
        return

    if not entries:
        await message.answer("Записей в журнале пока нет.")
        return

    lines = ["<b>Журнал действий</b>", ""]
    for entry in entries:
        title = titles.get(entry["chat_id"], str(entry["chat_id"]))
        lines.append(escape(format_audit_line(entry, chat_title=title)))
    await send_html_parts(message, "\n".join(lines))
