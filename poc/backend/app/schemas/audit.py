"""Sprint 15 — audit log schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None
    actor_role: str | None
    tenant_id: int | None
    action: str
    target_type: str | None
    target_id: int | None
    payload: dict[str, Any] | None
    created_at: datetime
