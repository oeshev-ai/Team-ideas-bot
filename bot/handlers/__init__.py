"""Пакет хендлеров: отдельные роутеры для группы и лички."""

from aiogram import Router

from bot.handlers.audit import router as audit_router
from bot.handlers.export import router as export_router
from bot.handlers.group import router as group_commands_router
from bot.handlers.moderation import router as moderation_router
from bot.handlers.start import router as start_router
from bot.handlers.tasks import router as tasks_router
from bot.middlewares import IncomingCommandMiddleware


def setup_routers() -> tuple[Router, Router]:
    """Собрать group_router и private_router без фильтров типа чата.

    Фильтры chat.type навешиваются в app.py при регистрации в диспетчере.
    """
    group_router = Router(name="group")
    group_router.message.middleware(IncomingCommandMiddleware())
    group_router.include_router(group_commands_router)

    private_router = Router(name="private")
    private_router.message.middleware(IncomingCommandMiddleware())
    private_router.include_router(start_router)
    private_router.include_router(tasks_router)
    private_router.include_router(moderation_router)
    private_router.include_router(export_router)
    private_router.include_router(audit_router)

    return group_router, private_router
