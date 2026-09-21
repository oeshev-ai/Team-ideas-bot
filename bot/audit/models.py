"""Модели журнала действий."""

from __future__ import annotations

from typing import TypedDict

AUDIT_LIMIT = 20
DETAILS_LIMIT = 200


class AuditEntry(TypedDict):
    """Запись журнала действий."""

    id: int
    chat_id: int
    user_id: int
    username: str | None
    action: str
    target_id: int | None
    details: str | None
    created_at: str
