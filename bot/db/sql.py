"""Вспомогательные SQL-функции и константы для задач."""

from __future__ import annotations

TASK_COLUMNS = (
    "id, chat_id, user_id, username, text, created_at, status, deleted_at, deleted_by"
)


def escape_like(value: str) -> str:
    """Экранировать спецсимволы LIKE (% _ !), чтобы искать их как обычный текст."""
    return (
        value.replace("!", "!!")
        .replace("%", "!%")
        .replace("_", "!_")
    )


def unicode_lower(value: object) -> str:
    """Привести значение к нижнему регистру с учётом кириллицы.

    Встроенный LOWER() SQLite обрабатывает только ASCII, поэтому для поиска
    регистрируется эта функция.
    """
    if value is None:
        return ""
    return str(value).casefold()
