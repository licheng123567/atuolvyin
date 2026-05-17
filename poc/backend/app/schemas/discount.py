"""v1.6 — Discount offer schemas (协商打折 / 减免审批)。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

OfferType = Literal[
    "principal_discount", "late_fee_waive", "installment", "long_overdue_compromise"
]
OfferStatus = Literal[
    "pending_supervisor", "pending_admin", "approved", "rejected", "executed", "expired"
]
ApproverRole = Literal["supervisor", "admin"]
ApplicantRole = Literal["agent", "supervisor"]


class DiscountOfferCreate(BaseModel):
    offer_type: OfferType
    original_amount: Decimal = Field(gt=0)
    proposed_amount: Decimal = Field(ge=0)
    installment_months: int | None = Field(None, ge=2, le=24)
    reason: str = Field(min_length=5, max_length=500)


class DiscountActionRequest(BaseModel):
    note: str | None = Field(None, max_length=500)


class DiscountRejectRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


class DiscountOfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    case_id: int
    provider_id: int | None = None
    applicant_user_id: int | None
    applicant_role: ApplicantRole
    applicant_name: str | None = None
    case_owner: str | None = None
    case_building: str | None = None
    project_name: str | None = None
    offer_type: OfferType
    offer_type_label: str = ""
    original_amount: Decimal
    proposed_amount: Decimal
    discount_pct: int
    installment_months: int | None
    reason: str
    status: OfferStatus
    approver_role_required: ApproverRole
    approved_by_user_id: int | None
    approved_by_name: str | None = None
    approved_at: datetime | None
    rejected_reason: str | None
    expires_at: datetime
    audit_trail: list[dict[str, Any]]
    created_at: datetime
