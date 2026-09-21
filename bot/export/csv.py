"""Экспорт задач в CSV для Excel."""

from __future__ import annotations

import csv
import io

from aiogram.types import BufferedInputFile

from bot.db.models import Task
from bot.export.common import export_date


def build_csv_file(
    tasks: list[Task],
    chat_id: int,
    *,
    filename: str | None = None,
) -> BufferedInputFile:
    """Собрать CSV (utf-8-sig, разделитель ';') для отправки в Telegram."""
    buffer = io.StringIO()
    writer = csv.writer(
        buffer,
        delimiter=";",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )
    writer.writerow(["id", "created_at", "status", "username", "user_id", "text"])
    for task in tasks:
        writer.writerow(
            [
                task["id"],
                task["created_at"],
                task["status"],
                task["username"] or "",
                task["user_id"],
                task["text"],
            ]
        )

    data = buffer.getvalue().encode("utf-8-sig")
    filename = filename or f"tasks_{chat_id}_{export_date()}.csv"
    return BufferedInputFile(file=data, filename=filename)
