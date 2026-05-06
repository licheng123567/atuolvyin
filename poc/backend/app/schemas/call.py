from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .common import PaginationQuery


class CallListQuery(PaginationQuery):
    case_id: int | None = None
    status: str | None = None


class CallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    case_id: int | None
    initiated_by: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_sec: int | None
    billable_duration: int | None
    result_tag: str | None
    risk_flagged: bool
    status: str
    created_at: datetime


class CallMinuteQuotaStatus(BaseModel):
    tenant_id: int
    year_month: str
    used_minutes: int
    quota: int | None
    remaining: int | None
    pct_used: float | None
    is_exhausted: bool


# ── Sprint 3a: calls_v1 schemas ───────────────────────────────


class CallUploadResponse(BaseModel):
    call_id: int
    status: str


class CallListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int | None
    callee_phone_masked: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_sec: int | None
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
    segments: list[TranscriptSegment] | None
    asr_model: str | None


class AnalysisResultOut(BaseModel):
    summary: str | None
    intent: str | None
    promise_date: str | None
    excuse_category: str | None
    compliance_disclosed: bool | None
    risk_keywords: list[str] | None
    confidence: float | None
    needs_review: bool


class CallDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int | None
    callee_phone_masked: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_sec: int | None
    recording_url: str | None
    status: str
    transcript: TranscriptOut | None
    analysis: AnalysisResultOut | None
    created_at: datetime


# ── Sprint 4: realtime call schemas ───────────────────────────


class DialRequestIn(BaseModel):
    case_id: int
    mode: str = "push"  # "push" | "qr"


class DialRequestOut(BaseModel):
    call_id: int
    status: str  # "dispatched" (push 模式) / "qr_pending" (qr 模式)
    qr_payload: str | None = None  # autoluyin://dial?call_id=...&token=...
    expires_at: datetime | None = None  # 仅 qr 模式


class DialInfoOut(BaseModel):
    """坐席 App 扫码后获取的案件信息（手机号已脱敏，密文用于实际拨号）。"""

    call_id: int
    case_id: int
    owner_name: str
    owner_phone_masked: str
    owner_phone_enc: str  # AES 密文，App 端解密拨号
    address: str | None
    debt_amount: float | None
    months_overdue: int | None


class CallTagPatch(BaseModel):
    intent: str | None = None
    promise_date: str | None = None
    promise_amount: float | None = None
    notes: str | None = None


class CallTagOut(BaseModel):
    call_id: int
    intent: str | None
    promise_date: str | None
    promise_amount: float | None
    summary: str | None
    user_confirmed_at: datetime | None


class SuggestionFeedbackIn(BaseModel):
    action: str  # "adopt" | "ignore"
    suggestion_text: str | None = None
    script_template_id: int | None = None
