"""Sprint 16.2 — Project (物业项目) schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    property_pm_user_id: int | None = None
    provider_pm_user_id: int | None = None
    provider_id: int | None = None
    plan_start: datetime | None = None
    plan_end: datetime | None = None
    description: str | None = None
    allow_internal_assist: bool = False


class ProjectUpdateIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    property_pm_user_id: int | None = None
    provider_pm_user_id: int | None = None
    provider_id: int | None = None
    plan_start: datetime | None = None
    plan_end: datetime | None = None
    description: str | None = None
    status: str | None = Field(None, pattern=r"^(active|paused|closed)$")
    allow_internal_assist: bool | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    name: str
    provider_id: int | None
    provider_name: str | None = None
    property_pm_user_id: int | None
    property_pm_name: str | None = None
    provider_pm_user_id: int | None
    provider_pm_name: str | None = None
    plan_start: datetime | None
    plan_end: datetime | None
    status: str
    description: str | None
    allow_internal_assist: bool = False
    case_count: int = 0
    created_at: datetime
