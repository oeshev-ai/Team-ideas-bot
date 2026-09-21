"""Команды модерации в личке: /delete, /stats, /chats."""

from __future__ import annotations

import logging
from html import escape

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.audit.repository import AuditRepository
from bot.db.tasks import TaskRepository
from bot.handlers.common import parse_task_id, send_html_parts, write_audit
from bot.permissions.access import ChatAccessService

logger = logging.getLogger(__name__)

router = Router(name="moderation")


@router.message(Command("delete"))
async def cmd_delete(
    message: Message,
    command: CommandObject,
    tasks: TaskRepository,
    bot: Bot,
    audit: AuditRepository,
    access: ChatAccessService,
) -> None:
    """Мягко удалить задачу. Только админ чата, где она создана."""
    if message.from_user is None:
        await message.answer("Не могу определить отправителя.")
        return

    task_id = parse_task_id(command.args)
    if task_id is None:
        await message.answer(
            "Укажите номер задачи.\nПример: <code>/delete 12</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        task = await tasks.get_task_by_id(task_id)
        chats = await access.get_accessible_chats(bot, tasks, message.from_user.id)
        allowed = {item.chat_id: item for item in chats}
        if task is None or task["status"] == "deleted" or task["chat_id"] not in allowed:
            await message.answer("Задача не найдена или нет доступа.")
            return

        if not allowed[task["chat_id"]].is_admin:
            reason = "Удалять задачи может только администратор."
            await write_audit(
                audit,
                message,
                "denied",
                target_id=task_id,
                details=reason,
                chat_id=task["chat_id"],
            )
            await message.answer(reason)
            return

        deleted = await tasks.soft_delete(
            task["chat_id"], task_id, message.from_user.id
        )
    except Exception:
        logger.exception("Ошибка при удалении задачи #%s", task_id)
        await message.answer("Не удалось удалить задачу. Попробуйте ещё раз.")
        return

    if deleted:
        await write_audit(
            audit,
            message,
            "delete",
            target_id=task_id,
            details=message.from_user.username or str(message.from_user.id),
            chat_id=task["chat_id"],
        )
        await message.answer(f"Задача #{task_id} удалена.")
    else:
        await message.answer("Задача не найдена или нет доступа.")


@router.message(Command("stats"))
async def cmd_stats(
    message: Message,
    bot: Bot,
    tasks: TaskRepository,
    access: ChatAccessService,
) -> None:
    """Статистика по всем доступным чатам."""
    if message.from_user is None:
        await message.answer("Не могу определить отправителя.")
        return

    try:
        chats = await access.get_accessible_chats(bot, tasks, message.from_user.id)
        chat_ids = [item.chat_id for item in chats]
        stats = await tasks.get_user_stats_for_chats(message.from_user.id, chat_ids)
    except Exception:
        logger.exception("Ошибка при сборе статистики")
        await message.answer("Не удалось получить статистику. Попробуйте ещё раз.")
        return

    text = (
        "<b>Статистика доступных чатов</b>\n\n"
        f"open: {stats['open']}\n"
        f"done: {stats['done']}\n"
        f"deleted: {stats['deleted']}\n\n"
        f"Добавлено вами: {stats['user_tasks']}"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(Command("chats"))
async def cmd_chats(
    message: Message,
    bot: Bot,
    tasks: TaskRepository,
    access: ChatAccessService,
) -> None:
    """Список доступных чатов, роли и число открытых задач."""
    if message.from_user is None:
        await message.answer("Не могу определить отправителя.")
        return

    try:
        chats = await access.get_accessible_chats(bot, tasks, message.from_user.id)
        if not chats:
            await message.answer(
                "Нет доступных чатов с задачами. Добавьте бота в группу команды."
            )
            return
        chat_ids = [item.chat_id for item in chats]
        counts = await tasks.get_open_counts_by_chat(chat_ids)
        titles = await access.titles_for(bot, chat_ids)
    except Exception:
        logger.exception("Ошибка при получении списка чатов")
        await message.answer("Не удалось получить список чатов. Попробуйте ещё раз.")
        return

    lines = ["<b>Доступные чаты</b>", ""]
    for item in chats:
        title = escape(titles.get(item.chat_id, str(item.chat_id)))
        open_count = counts.get(item.chat_id, 0)
        lines.append(f"• {title} (chat_id: <code>{item.chat_id}</code>)")
        lines.append(
            f"  Роль: {item.role_label} | Открытых задач: {open_count}"
        )
        lines.append("")
    await send_html_parts(message, "\n".join(lines).rstrip())
