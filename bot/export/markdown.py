"""Экспорт задач в Markdown."""

from __future__ import annotations

from aiogram.types import BufferedInputFile

from bot.db.models import Task
from bot.export.common import author_label, export_date, status_label


def build_markdown_file(
    tasks: list[Task],
    chat_id: int,
    *,
    filename: str | None = None,
    heading: str | None = None,
) -> BufferedInputFile:
    """Собрать Markdown-отчёт по задачам чата."""
    date = export_date()
    lines: list[str] = [
        heading or f"# Задачи чата `{chat_id}`",
        "",
        f"Дата экспорта: {date}",
        f"Всего задач: {len(tasks)}",
        "",
    ]

    if not tasks:
        lines.append("_Задач пока нет._")
    else:
        lines.append("## Список")
        lines.append("")
        for task in tasks:
            lines.append(
                f"### #{task['id']} · {status_label(task['status'])} · "
                f"{task['created_at']} · {author_label(task)}"
            )
            lines.append("")
            lines.append(task["text"])
            lines.append("")

    data = "\n".join(lines).encode("utf-8")
    filename = filename or f"tasks_{chat_id}_{date}.md"
    return BufferedInputFile(file=data, filename=filename)
