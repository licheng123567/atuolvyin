from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    credit_code: str | None = Field(None, max_length=50)
    admin_phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    plan: Literal["trial", "standard", "premium"] = "trial"
    monthly_minute_quota: int | None = Field(None, ge=0, le=100000)

    model_config = ConfigDict(str_strip_whitespace=True)


class TenantQuotaUpdate(BaseModel):
    monthly_minute_quota: int = Field(..., ge=0, le=100000)


class TenantRenewIn(BaseModel):
    """续费 / 变更套餐 — 共用同一个 body."""

    expires_at: datetime
    plan: Literal["trial", "standard", "premium"] | None = None
    monthly_minute_quota: int | None = Field(None, ge=0, le=100000)


class TenantDisableIn(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)

    model_config = ConfigDict(str_strip_whitespace=True)


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    credit_code: str | None
    admin_phone_masked: str  # computed by service layer
    plan: str
    monthly_minute_quota: int | None
    expires_at: datetime | None
    is_active: bool
    is_trial: bool
    disabled_reason: str | None
    disabled_at: datetime | None
    created_at: datetime


class TenantTrialOut(BaseModel):
    """Trial-list item with computed days_remaining."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    plan: str
    admin_phone_masked: str
    expires_at: datetime | None
    days_remaining: int | None  # None when no expires_at
    is_active: bool
    created_at: datetime
