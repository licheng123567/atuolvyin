"""Sprint 10 — Admin Settlement schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SettlementStatus = Literal["DRAFT", "CONFIRMED", "PAID", "DISPUTED"]
DisputeStatus = Literal["open", "resolved", "rejected"]
# v0.6.0 — 计费方式枚举(对应 SettlementStatement.billing_method 列)
BillingMethod = Literal["monthly_fee", "per_case", "percent_of_recovered"]


class SettlementOut(BaseModel):
    """List item & action result for a settlement statement."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    provider_id: int | None = None
    provider_name: str | None = None
    period_start: datetime
    period_end: datetime
    total_amount: Decimal
    status: SettlementStatus
    payment_proof_url: str | None = None
    confirmed_at: datetime | None = None
    paid_at: datetime | None = None
    billing_method: BillingMethod | None = None  # v0.6.0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DisputeOut(BaseModel):
    """A single DisputeRecord."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    statement_id: int
    reason: str
    status: DisputeStatus
    resolution: str | None = None
    submitted_by: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SettlementDetailOut(SettlementOut):
    """Detail view: includes embedded dispute history."""

    disputes: list[DisputeOut] = Field(default_factory=list)


class PayIn(BaseModel):
    """Body for PATCH /settlements/{id}/pay."""

    payment_proof_url: str | None = Field(None, max_length=2048)


class DisputeIn(BaseModel):
    """Body for POST /settlements/{id}/dispute."""

    reason: str = Field(min_length=1, max_length=2000)
