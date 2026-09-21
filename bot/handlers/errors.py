"""Глобальный обработчик ошибок, чтобы polling не падал."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)


def register(router: Router) -> None:
    """Подключить обработчик ошибок к корневому роутеру."""

    @router.error()
    async def on_error(event: ErrorEvent) -> None:
        """Перехватить необработанные ошибки."""
        logger.error(
            "Необработанная ошибка: %s",
            event.exception,
            exc_info=event.exception,
        )
        update = event.update
        if update.message:
            try:
                await update.message.answer(
                    "Произошла внутренняя ошибка. Попробуйте ещё раз."
                )
            except Exception:
                logger.exception("Не удалось отправить сообщение об ошибке")
