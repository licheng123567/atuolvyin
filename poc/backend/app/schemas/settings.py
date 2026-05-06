"""Sprint 8.5 — Tenant settings schemas (PRD §3.14)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TenantSettingsOut(BaseModel):
    recording_mode: Literal["live", "post", "auto"]
    l3_hangup_enabled: bool
    contact_freq_max: int
    retention_days: int


class TenantSettingsUpdate(BaseModel):
    recording_mode: Literal["live", "post", "auto"] | None = None
    l3_hangup_enabled: bool | None = None
    contact_freq_max: int | None = Field(None, ge=1, le=30)
    retention_days: int | None = Field(None, ge=30, le=3650)
