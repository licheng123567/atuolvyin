"""Sprint 16.3 — 法务结算账单 schema (PRD §20.4)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator


class GenerateInvoiceRequest(BaseModel):
    period_start: datetime
    period_end: datetime

    @model_validator(mode="after")
    def _ordered(self) -> GenerateInvoiceRequest:
        if self.period_end <= self.period_start:
            raise ValueError("period_end must be after period_start")
        return self


class LegalPlatformInvoiceOut(BaseModel):
    id: int
    law_firm_id: int
    period_start: datetime
    period_end: datetime
    total_amount: Decimal
    order_count: int
    invoice_lines: list[dict[str, Any]] | None
    status: str
    confirmed_at: datetime | None
    paid_at: datetime | None
    payment_proof_url: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConfirmInvoiceRequest(BaseModel):
    notes: str | None = Field(None, max_length=2000)


class MarkPaidRequest(BaseModel):
    payment_proof_url: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=2000)
