"""Sprint 10 — Admin Settlement schemas."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


SettlementStatus = Literal["DRAFT", "CONFIRMED", "PAID", "DISPUTED"]
DisputeStatus = Literal["open", "resolved", "rejected"]


class SettlementOut(BaseModel):
    """List item & action result for a settlement statement."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    provider_id: Optional[int] = None
    provider_name: Optional[str] = None
    period_start: datetime
    period_end: datetime
    total_amount: Decimal
    status: SettlementStatus
    payment_proof_url: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DisputeOut(BaseModel):
    """A single DisputeRecord."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    statement_id: int
    reason: str
    status: DisputeStatus
    resolution: Optional[str] = None
    submitted_by: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SettlementDetailOut(SettlementOut):
    """Detail view: includes embedded dispute history."""

    disputes: list[DisputeOut] = Field(default_factory=list)


class PayIn(BaseModel):
    """Body for PATCH /settlements/{id}/pay."""

    payment_proof_url: Optional[str] = Field(None, max_length=2048)


class DisputeIn(BaseModel):
    """Body for POST /settlements/{id}/dispute."""

    reason: str = Field(min_length=1, max_length=2000)
