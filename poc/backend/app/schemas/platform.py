"""Sprint 10 — Platform-level schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ── Settlement overview (L1999) ─────────────────────────────────────


class SettlementSummaryItem(BaseModel):
    tenant_id: int
    tenant_name: str
    period_start: datetime
    period_end: datetime
    total_amount: Decimal
    status: str  # DRAFT / CONFIRMED / PAID / DISPUTED
    overdue_days: int  # days past period_end without payment


class SettlementOverviewOut(BaseModel):
    total_pending: Decimal
    total_paid_month: Decimal
    overdue_count: int
    items: list[SettlementSummaryItem]


# ── Customer followup (L2000) ───────────────────────────────────────


class CustomerFollowupIn(BaseModel):
    tenant_id: int
    note: str = Field(min_length=1, max_length=4000)
    follow_up_at: datetime | None = None


class CustomerFollowupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    tenant_name: str | None = None
    note: str
    follow_up_at: datetime | None
    created_by: int
    created_at: datetime


# ── System announcement (L2001) ─────────────────────────────────────


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
    audience: str = Field(default="all", pattern=r"^(all|role:[a-z_]+|tenant:\d+)$")
    publish_at: datetime | None = None


class AnnouncementPatchIn(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    body: str | None = Field(None, min_length=1, max_length=10000)
    audience: str | None = Field(None, pattern=r"^(all|role:[a-z_]+|tenant:\d+)$")
    publish_at: datetime | None = None


class AnnouncementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    audience: str
    publish_at: datetime | None
    created_by: int
    created_at: datetime


# ── LLM prompt template (L1969) ─────────────────────────────────────


class LLMPromptIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    body: str = Field(min_length=1, max_length=20000)
    notes: str | None = Field(None, max_length=2000)


class LLMPromptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    version: int
    body: str
    notes: str | None
    is_active: bool
    created_by: int
    created_at: datetime


class LLMPromptActivateIn(BaseModel):
    is_active: bool


# ── Blockchain config (L1972) ───────────────────────────────────────


class BlockchainConfigIn(BaseModel):
    provider: Literal["antchain", "fisco-bcos", "mock"]
    api_endpoint: str = Field(min_length=1, max_length=500)
    api_key: str | None = Field(None, max_length=500)
    is_active: bool = False


class BlockchainConfigOut(BaseModel):
    id: int
    provider: str
    api_endpoint: str
    has_api_key: bool  # never echo the key back
    is_active: bool
    last_failure_at: datetime | None
    last_failure_reason: str | None
    updated_at: datetime


# ── SMS config (短信中心 028lk) ─────────────────────────────────────


class SmsConfigIn(BaseModel):
    secret_name: str = Field(min_length=1, max_length=128)
    secret_key: str | None = Field(None, min_length=1, max_length=500)  # None=不改；空串422
    sign_name: str = Field(default="", max_length=64)
    otp_template_id: str | None = Field(None, max_length=64)
    is_active: bool = False


class SmsConfigOut(BaseModel):
    id: int
    secret_name: str
    sign_name: str
    otp_template_id: str | None
    has_secret_key: bool  # never echo the key back
    is_active: bool
    last_failure_at: datetime | None
    last_failure_reason: str | None
    updated_at: datetime
