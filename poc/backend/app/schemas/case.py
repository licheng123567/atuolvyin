from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import PaginationQuery


class CaseListQuery(PaginationQuery):
    status: str | None = None
    pool_type: str | None = None
    assigned_to: int | None = None
    keyword: str | None = None


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    project_id: int | None
    owner_id: int
    assigned_to: int | None
    pool_type: str
    stage: str
    amount_owed: Decimal | None
    months_overdue: int | None
    priority_score: int
    last_contact_at: datetime | None
    monthly_contact_count: int
    status: str
    created_at: datetime
    updated_at: datetime


class CaseAssignRequest(BaseModel):
    case_ids: list[int] = Field(..., min_length=1, max_length=500)
    assign_to: int


class CaseImportRow(BaseModel):
    name: str = Field(..., min_length=1)
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    building: str | None = None
    room: str | None = None
    amount_owed: Decimal | None = None
    months_overdue: int | None = None
    notes: str | None = None  # 欠费情况说明（拒缴/暂时困难/失联等）


class OwnerInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str | None = None        # decrypted, only for agent_internal
    phone_masked: str
    building: str | None
    room: str | None
    do_not_call: bool


class CaseWithOwnerResponse(BaseModel):
    id: int
    tenant_id: int
    project_id: int | None
    owner: OwnerInfo
    assigned_to: int | None
    pool_type: str
    stage: str
    amount_owed: Decimal | None
    months_overdue: int | None
    priority_score: int
    last_contact_at: datetime | None
    monthly_contact_count: int
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class CaseImportRequest(BaseModel):
    project_id: int | None = None
    rows: list[CaseImportRow] = Field(..., min_length=1, max_length=500)


class CaseImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


class CaseStageUpdate(BaseModel):
    stage: Literal["new", "in_progress", "promised", "paid", "escalated", "closed"]


class CaseAssignResponse(BaseModel):
    updated_count: int


# ── Sprint 3b: case detail with call timeline ──────────────────


class CaseCallItem(BaseModel):
    id: int
    started_at: datetime | None
    duration_sec: int | None
    status: str
    transcript_preview: str | None
    result_tag: str | None
    confidence: float | None
    agent_name: str | None


class TimelineEvent(BaseModel):
    type: str
    ts: datetime
    actor: str | None
    note: str | None


class CaseDetailResponse(BaseModel):
    id: int
    tenant_id: int
    project_id: int | None
    project_name: str | None = None
    owner: OwnerInfo
    assigned_to: int | None
    assigned_role: str | None = None  # v1.4 — 协作来源 badge：agent_internal / agent_external / null
    pool_type: str
    stage: str
    amount_owed: Decimal | None
    months_overdue: int | None
    priority_score: int
    last_contact_at: datetime | None
    monthly_contact_count: int
    status: str
    created_at: datetime
    updated_at: datetime
    calls: list[CaseCallItem]
    timeline_events: list[TimelineEvent]
