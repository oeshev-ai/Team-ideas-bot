"""Команда /export в личке — все доступные чаты в один файл."""

from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.audit.repository import AuditRepository
from bot.db.tasks import TaskRepository
from bot.export import build_csv_file, build_markdown_file
from bot.export.common import export_date
from bot.handlers.common import write_audit_for_chats
from bot.permissions.access import ChatAccessService

logger = logging.getLogger(__name__)

router = Router(name="export")


@router.message(Command("export"))
async def cmd_export(
    message: Message,
    command: CommandObject,
    tasks: TaskRepository,
    bot: Bot,
    audit: AuditRepository,
    access: ChatAccessService,
) -> None:
    """Выгрузить задачи всех доступных чатов в CSV или Markdown."""
    if message.from_user is None:
        await message.answer("Не могу определить отправителя.")
        return

    fmt = (command.args or "").strip().lower()
    if fmt not in {"csv", "md"}:
        await message.answer(
            "Укажите формат экспорта.\n"
            "<code>/export csv</code> — таблица для Excel\n"
            "<code>/export md</code> — Markdown-файл",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        chats = await access.get_accessible_chats(bot, tasks, message.from_user.id)
        chat_ids = [item.chat_id for item in chats]
        items = await tasks.get_all_tasks_for_chats(chat_ids)
    except Exception:
        logger.exception("Ошибка при экспорте задач")
        await message.answer("Не удалось подготовить файл. Попробуйте ещё раз.")
        return

    if not items:
        await message.answer("Нет задач для экспорта в доступных чатах.")
        return

    user_id = message.from_user.id
    date = export_date()
    try:
        if fmt == "csv":
            document = build_csv_file(
                items,
                user_id,
                filename=f"tasks_{user_id}_{date}.csv",
            )
            caption = "Экспорт задач доступных чатов в CSV"
        else:
            document = build_markdown_file(
                items,
                user_id,
                filename=f"tasks_{user_id}_{date}.md",
                heading="# Задачи доступных чатов",
            )
            caption = "Экспорт задач доступных чатов в Markdown"
        file_size = len(document.data)
        await message.answer_document(document=document, caption=caption)
        logger.info(
            "Отправлен файл экспорта name=%s size=%s",
            document.filename,
            file_size,
        )
        await write_audit_for_chats(audit, message, "export", chat_ids, details=fmt)
    except Exception:
        logger.exception("Ошибка при отправке файла экспорта")
        await message.answer("Не удалось отправить файл. Попробуйте ещё раз.")
