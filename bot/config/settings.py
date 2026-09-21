"""Загрузка настроек из .env и переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


@dataclass(frozen=True)
class Settings:
    """Настройки приложения.

    Attributes:
        bot_token: Токен Telegram-бота.
        db_path: Путь к файлу базы SQLite.
        log_level: Уровень технического лога (DEBUG/INFO/...).
    """

    bot_token: str
    db_path: str
    log_level: str


def parse_log_level(raw: str | None) -> str:
    """Вернуть допустимый уровень лога, по умолчанию INFO."""
    level = (raw or "INFO").strip().upper() or "INFO"
    if level not in VALID_LOG_LEVELS:
        return "INFO"
    return level


def load_settings() -> Settings:
    """Прочитать настройки из окружения.

    Raises:
        RuntimeError: Если не задан BOT_TOKEN.
    """
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError(
            "Не задан BOT_TOKEN. Укажите токен Telegram-бота в файле .env "
            "или в переменных окружения."
        )

    db_path = os.getenv("DB_PATH", "tasks.db").strip() or "tasks.db"
    log_level = parse_log_level(os.getenv("LOG_LEVEL"))
    return Settings(bot_token=bot_token, db_path=db_path, log_level=log_level)
