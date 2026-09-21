"""Команда /add — регистрируется и в группе, и в личке."""

from __future__ import annotations

import logging

from aiogram.enums import ParseMode
from aiogram.filters import CommandObject
from aiogram.types import Message

from bot.audit.repository import AuditRepository
from bot.db.tasks import TaskRepository
from bot.handlers.common import write_audit

logger = logging.getLogger(__name__)


async def cmd_add(
    message: Message,
    command: CommandObject,
    tasks: TaskRepository,
    audit: AuditRepository,
) -> None:
    """Добавить новую идею или задачу в текущий чат."""
    if message.from_user is None:
        await message.answer("Не могу определить отправителя.")
        return

    text = (command.args or "").strip()
    if not text:
        await message.answer(
            "Напишите текст после команды.\n"
            "Пример: <code>/add Купить маркеры для доски</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        task_id = await tasks.add_task(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            username=message.from_user.username,
            text=text,
        )
    except Exception:
        logger.exception("Ошибка при добавлении задачи")
        await message.answer("Не удалось сохранить задачу. Попробуйте ещё раз.")
        return

    await write_audit(audit, message, "add", target_id=task_id, details=text[:200])
    await message.answer(f"✅ Сохранил #{task_id}")
