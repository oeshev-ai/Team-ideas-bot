"""Команды работы с задачами в личке: /add, /list, /search, /done."""

from __future__ import annotations

import logging
from html import escape

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.audit.repository import AuditRepository
from bot.db.tasks import TaskRepository
from bot.handlers.add import cmd_add
from bot.handlers.common import (
    NO_ACCESS_TEXT,
    build_task_list_text,
    parse_task_id,
    send_html_parts,
    write_audit,
    write_audit_for_chats,
)
from bot.permissions.access import ChatAccessService
from bot.permissions.checks import resolve_close_role

logger = logging.getLogger(__name__)

router = Router(name="tasks")
router.message.register(cmd_add, Command("add"))


@router.message(Command("list"))
async def cmd_list(
    message: Message,
    bot: Bot,
    tasks: TaskRepository,
    access: ChatAccessService,
) -> None:
    """Показать открытые задачи всех доступных чатов."""
    if message.from_user is None:
        await message.answer("Не могу определить отправителя.")
        return

    try:
        chats = await access.get_accessible_chats(bot, tasks, message.from_user.id)
        chat_ids = [item.chat_id for item in chats]
        if not chat_ids:
            await message.answer(NO_ACCESS_TEXT)
            return
        items, has_more = await tasks.get_tasks_for_chats(chat_ids)
        titles = await access.titles_for(bot, [task["chat_id"] for task in items])
    except Exception:
        logger.exception("Ошибка при получении списка задач")
        await message.answer("Не удалось получить список. Попробуйте ещё раз.")
        return

    if not items:
        await message.answer("Открытых задач нет.")
        return

    text = build_task_list_text(
        items,
        title="<b>Открытые задачи</b>",
        has_more=has_more,
        chat_titles=titles,
    )
    await send_html_parts(message, text)


@router.message(Command("done"))
async def cmd_done(
    message: Message,
    command: CommandObject,
    tasks: TaskRepository,
    bot: Bot,
    audit: AuditRepository,
    access: ChatAccessService,
) -> None:
    """Закрыть задачу из доступного чата: автор или админ этого чата."""
    if message.from_user is None:
        await message.answer("Не могу определить отправителя.")
        return

    task_id = parse_task_id(command.args)
    if task_id is None:
        await message.answer(
            "Укажите номер задачи.\nПример: <code>/done 12</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        task = await tasks.get_task_by_id(task_id)
        chats = await access.get_accessible_chats(bot, tasks, message.from_user.id)
        allowed_ids = {item.chat_id for item in chats}
        if task is None or task["status"] != "open" or task["chat_id"] not in allowed_ids:
            await message.answer("Задача не найдена или нет доступа.")
            return

        role = resolve_close_role(message.from_user.id, task, chats)
        if role is None:
            reason = "Закрывать чужие задачи может только автор или администратор."
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

        updated = await tasks.mark_done(task["chat_id"], task_id)
    except Exception:
        logger.exception("Ошибка при отметке задачи #%s", task_id)
        await message.answer("Не удалось обновить задачу. Попробуйте ещё раз.")
        return

    if updated:
        await write_audit(
            audit,
            message,
            "done",
            target_id=task_id,
            details=role,
            chat_id=task["chat_id"],
        )
        await message.answer(f"Задача #{task_id} отмечена выполненной")
    else:
        await message.answer("Задача не найдена или нет доступа.")


@router.message(Command("search"))
async def cmd_search(
    message: Message,
    command: CommandObject,
    tasks: TaskRepository,
    bot: Bot,
    audit: AuditRepository,
    access: ChatAccessService,
) -> None:
    """Поиск по открытым задачам всех доступных чатов."""
    query = (command.args or "").strip()
    if not query:
        await message.answer(
            "Укажите текст для поиска.\nПример: <code>/search маркеры</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    if message.from_user is None:
        await message.answer("Не могу определить отправителя.")
        return

    try:
        chats = await access.get_accessible_chats(bot, tasks, message.from_user.id)
        chat_ids = [item.chat_id for item in chats]
        if not chat_ids:
            await message.answer(NO_ACCESS_TEXT)
            return
        items, has_more = await tasks.search_tasks_for_chats(chat_ids, query)
        titles = await access.titles_for(bot, [task["chat_id"] for task in items])
    except Exception:
        logger.exception("Ошибка при поиске задач")
        await message.answer("Не удалось выполнить поиск. Попробуйте ещё раз.")
        return

    await write_audit_for_chats(audit, message, "search", chat_ids, details=query)

    if not items:
        await message.answer("Ничего не найдено.")
        return

    escaped_query = escape(query)
    text = build_task_list_text(
        items,
        title=f"<b>Результаты поиска:</b> {escaped_query}",
        has_more=has_more,
        chat_titles=titles,
    )
    await send_html_parts(message, text)
