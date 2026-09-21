"""Сборка приложения: логи, БД, диспетчер и polling."""

from __future__ import annotations

import asyncio
import logging
import os

from aiogram import F, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
)
from dotenv import load_dotenv

from bot.audit.repository import AuditRepository
from bot.config.settings import load_settings
from bot.config.techlog import setup_logging
from bot.db.connection import Database
from bot.db.tasks import TaskRepository
from bot.handlers import setup_routers
from bot.handlers.errors import register as register_errors
from bot.permissions.access import ChatAccessService
from bot.permissions.cache import AdminCache

logger = logging.getLogger(__name__)

GROUP_COMMANDS = [
    BotCommand(command="start", description="Справка"),
    BotCommand(command="add", description="Добавить идею или задачу"),
]

PRIVATE_COMMANDS = [
    BotCommand(command="start", description="Приветствие"),
    BotCommand(command="help", description="Справка по командам"),
    BotCommand(command="add", description="Добавить задачу"),
    BotCommand(command="list", description="Список открытых задач"),
    BotCommand(command="done", description="Отметить задачу выполненной"),
    BotCommand(command="search", description="Поиск по задачам"),
    BotCommand(command="export", description="Выгрузить задачи: csv или md"),
    BotCommand(command="delete", description="Удалить задачу (администратор)"),
    BotCommand(command="stats", description="Статистика задач"),
    BotCommand(command="audit", description="Журнал действий (администратор)"),
    BotCommand(command="chats", description="Доступные чаты команды"),
]


async def main() -> None:
    """Настроить логи, открыть БД и начать polling."""
    load_dotenv()
    setup_logging(
        os.getenv("LOG_LEVEL", "INFO"),
        secrets=[os.getenv("BOT_TOKEN", "")],
    )
    logger.info("Запуск бота")

    try:
        settings = load_settings()
    except RuntimeError:
        logger.exception("Некорректная конфигурация")
        raise

    database = Database(settings.db_path)
    await database.connect()

    tasks = TaskRepository(database)
    audit = AuditRepository(database)
    await tasks.init_schema()
    await audit.init_schema()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    register_errors(dp)

    group_router, private_router = setup_routers()
    group_router.message.filter(F.chat.type.in_({"group", "supergroup"}))
    private_router.message.filter(F.chat.type == "private")
    dp.include_router(group_router)
    dp.include_router(private_router)

    dp["tasks"] = tasks
    dp["audit"] = audit
    dp["admin_cache"] = AdminCache()
    dp["access"] = ChatAccessService()

    try:
        await bot.set_my_commands(GROUP_COMMANDS, scope=BotCommandScopeAllGroupChats())
        await bot.set_my_commands(
            PRIVATE_COMMANDS,
            scope=BotCommandScopeAllPrivateChats(),
        )
        me = await bot.get_me()
        logger.info("Бот запущен: @%s (id=%s)", me.username, me.id)
        logger.info("Файл БД: %s", settings.db_path)
        await dp.start_polling(bot)
    finally:
        await database.close()
        logger.info("Бот остановлен")


def run() -> None:
    """Синхронная точка входа для python -m bot и main.py."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Остановка по Ctrl+C")
