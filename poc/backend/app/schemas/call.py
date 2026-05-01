from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .common import PaginationQuery


class CallListQuery(PaginationQuery):
    case_id: Optional[int] = None
    status: Optional[str] = None


class CallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    case_id: Optional[int]
    initiated_by: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_sec: Optional[int]
    billable_duration: Optional[int]
    result_tag: Optional[str]
    risk_flagged: bool
    status: str
    created_at: datetime


class CallMinuteQuotaStatus(BaseModel):
    tenant_id: int
    year_month: str
    used_minutes: int
    quota: Optional[int]
    remaining: Optional[int]
    pct_used: Optional[float]
    is_exhausted: bool


# ── Sprint 3a: calls_v1 schemas ───────────────────────────────


class CallUploadResponse(BaseModel):
    call_id: int
    status: str


class CallListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: Optional[int]
    callee_phone_masked: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_sec: Optional[int]
    status: str
    created_at: datetime


# ── Sprint 3b: transcript + analysis schemas ──────────────────


class TranscriptSegment(BaseModel):
    speaker: int
    start_ms: int
    end_ms: int
    text: str


class TranscriptOut(BaseModel):
    full_text: str
    segments: Optional[list[TranscriptSegment]]
    asr_model: Optional[str]


class AnalysisResultOut(BaseModel):
    summary: Optional[str]
    intent: Optional[str]
    promise_date: Optional[str]
    excuse_category: Optional[str]
    compliance_disclosed: Optional[bool]
    risk_keywords: Optional[list[str]]
    confidence: Optional[float]
    needs_review: bool


class CallDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: Optional[int]
    callee_phone_masked: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_sec: Optional[int]
    recording_url: Optional[str]
    status: str
    transcript: Optional[TranscriptOut]
    analysis: Optional[AnalysisResultOut]
    created_at: datetime


# ── Sprint 4: realtime call schemas ───────────────────────────


class DialRequestIn(BaseModel):
    case_id: int


class DialRequestOut(BaseModel):
    call_id: int
    status: str  # "dispatched"
