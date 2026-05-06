"""Sprint 13 — Legal Case schemas (legal role)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LEGAL_STAGES = (
    "pending_eval",
    "evidence_collection",
    "litigation_filed",
    "judgment_pending",
    "enforcing",
    "closed_won",
    "closed_lost",
    "closed_settled",
)

LegalStage = Literal[
    "pending_eval",
    "evidence_collection",
    "litigation_filed",
    "judgment_pending",
    "enforcing",
    "closed_won",
    "closed_lost",
    "closed_settled",
]


class LegalCaseCreate(BaseModel):
    case_id: int = Field(..., gt=0)
    stage: LegalStage = "pending_eval"
    amount_disputed: Decimal | None = Field(None, ge=0)
    notes: str | None = Field(None, max_length=4000)
    lawyer_name: str | None = Field(None, max_length=100)
    law_firm: str | None = Field(None, max_length=200)
    next_milestone: str | None = Field(None, max_length=500)

    model_config = ConfigDict(str_strip_whitespace=True)


class LegalCasePatch(BaseModel):
    stage: LegalStage | None = None
    amount_disputed: Decimal | None = Field(None, ge=0)
    lawyer_name: str | None = Field(None, max_length=100)
    law_firm: str | None = Field(None, max_length=200)
    next_milestone: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=4000)

    model_config = ConfigDict(str_strip_whitespace=True)


class LegalCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    case_id: int
    stage: str
    amount_disputed: Decimal | None
    lawyer_name: str | None
    law_firm: str | None
    next_milestone: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    # enrichments
    owner_name: str | None = None
    owner_phone_masked: str | None = None


class CollectionCaseRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stage: str
    amount_owed: Decimal | None
    months_overdue: int | None
    owner_name: str
    owner_phone_masked: str


class LegalCaseDetailOut(LegalCaseOut):
    collection_case: CollectionCaseRef | None = None
