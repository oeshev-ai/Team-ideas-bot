"""Общие детали экспорта: дата файла, автор, подпись статуса."""

from __future__ import annotations

from datetime import datetime, timezone

from bot.db.models import Task


def export_date() -> str:
    """Вернуть текущую дату UTC в формате YYYY-MM-DD."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def author_label(task: Task) -> str:
    """Собрать отображаемое имя автора."""
    if task["username"]:
        return f"@{task['username']}"
    return f"id:{task['user_id']}"


def status_label(status: str) -> str:
    """Человекочитаемый статус для Markdown."""
    mapping = {
        "open": "открыта",
        "done": "выполнена",
        "deleted": "удалена",
    }
    return mapping.get(status, status)
