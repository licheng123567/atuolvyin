from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .common import PaginationQuery


class CaseListQuery(PaginationQuery):
    status: Optional[str] = None
    pool_type: Optional[str] = None
    assigned_to: Optional[int] = None
    keyword: Optional[str] = None


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    project_id: Optional[int]
    owner_id: int
    assigned_to: Optional[int]
    pool_type: str
    stage: str
    amount_owed: Optional[Decimal]
    months_overdue: Optional[int]
    priority_score: int
    last_contact_at: Optional[datetime]
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
    building: Optional[str] = None
    room: Optional[str] = None
    amount_owed: Optional[Decimal] = None
    months_overdue: Optional[int] = None


class OwnerInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: Optional[str] = None        # decrypted, only for agent_internal
    phone_masked: str
    building: Optional[str]
    room: Optional[str]
    do_not_call: bool


class CaseWithOwnerResponse(BaseModel):
    id: int
    tenant_id: int
    project_id: Optional[int]
    owner: OwnerInfo
    assigned_to: Optional[int]
    pool_type: str
    stage: str
    amount_owed: Optional[Decimal]
    months_overdue: Optional[int]
    priority_score: int
    last_contact_at: Optional[datetime]
    monthly_contact_count: int
    status: str
    created_at: datetime
    updated_at: datetime


class CaseImportRequest(BaseModel):
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
    started_at: Optional[datetime]
    duration_sec: Optional[int]
    status: str
    transcript_preview: Optional[str]
    result_tag: Optional[str]
    confidence: Optional[float]
    agent_name: Optional[str]


class TimelineEvent(BaseModel):
    type: str
    ts: datetime
    actor: Optional[str]
    note: Optional[str]


class CaseDetailResponse(BaseModel):
    id: int
    tenant_id: int
    project_id: Optional[int]
    owner: OwnerInfo
    assigned_to: Optional[int]
    pool_type: str
    stage: str
    amount_owed: Optional[Decimal]
    months_overdue: Optional[int]
    priority_score: int
    last_contact_at: Optional[datetime]
    monthly_contact_count: int
    status: str
    created_at: datetime
    updated_at: datetime
    calls: list[CaseCallItem]
    timeline_events: list[TimelineEvent]
