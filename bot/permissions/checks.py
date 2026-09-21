"""Проверки прав на закрытие задач и типа чата."""

from __future__ import annotations

from aiogram.types import Chat

from bot.db.models import Task
from bot.permissions.access import ChatAccess


def is_private_chat(chat: Chat) -> bool:
    """Вернуть True, если сообщение пришло из личного чата с ботом."""
    return chat.type == "private"


def resolve_close_role(
    user_id: int,
    task: Task,
    access: list[ChatAccess],
) -> str | None:
    """Вернуть 'author'/'admin' или None, если закрывать нельзя.

    В личке смотрим чат, где задача создана: автор или админ этого чата.
    """
    if task["user_id"] == user_id:
        return "author"
    for item in access:
        if item.chat_id == task["chat_id"] and item.is_admin:
            return "admin"
    return None
