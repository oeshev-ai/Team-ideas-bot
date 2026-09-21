"""Модели записей таблицы tasks."""

from __future__ import annotations

from typing import TypedDict


class Task(TypedDict):
    """Запись задачи в базе данных."""

    id: int
    chat_id: int
    user_id: int
    username: str | None
    text: str
    created_at: str
    status: str
    deleted_at: str | None
    deleted_by: int | None


class ChatStats(TypedDict):
    """Сводка по задачам чата."""

    open: int
    done: int
    deleted: int
    user_tasks: int
