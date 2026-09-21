"""Технический лог: stdout и logs/bot.log с ротацией и маскированием секретов."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from bot.config.settings import parse_log_level

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_FILE_PATH = Path("logs") / "bot.log"
LOG_MAX_BYTES = 5_000_000
LOG_BACKUP_COUNT = 5


class RedactingFormatter(logging.Formatter):
    """Форматтер, который заменяет секреты на *** во всём тексте записи."""

    def __init__(self, fmt: str, secrets: list[str]) -> None:
        """Создать форматтер с маскированием.

        Args:
            fmt: Строка формата logging.
            secrets: Значения, которые нельзя писать в лог (токен и т.п.).
        """
        super().__init__(fmt)
        self._secrets = [item for item in secrets if item]

    def format(self, record: logging.LogRecord) -> str:
        """Собрать строку лога и вымарать секреты, включая traceback."""
        text = super().format(record)
        for secret in self._secrets:
            text = text.replace(secret, "***")
        return text


def setup_logging(level_name: str = "INFO", secrets: list[str] | None = None) -> None:
    """Настроить технический лог: stdout и logs/bot.log с ротацией.

    Папка logs создаётся автоматически. Токен и другие секреты маскируются.
    """
    log_dir = LOG_FILE_PATH.parent
    log_dir.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, parse_log_level(level_name), logging.INFO)
    formatter = RedactingFormatter(LOG_FORMAT, secrets or [])

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    file_handler = RotatingFileHandler(
        LOG_FILE_PATH,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
