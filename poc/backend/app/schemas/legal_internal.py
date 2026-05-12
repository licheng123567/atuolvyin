"""v1.9.0 — 物业内部法务处理环节 schemas。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ── action_type / close_reason 枚举 ────────────────────────────
ActionType = Literal[
    "contact_owner",
    "send_lawyer_letter",
    "send_notice",
    "mediation",
    "other",
]
CloseReason = Literal["paid", "promised", "uncollectible", "escalated"]


# ── PartnerLawFirm ─────────────────────────────────────────────
class PartnerLawFirmCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    contact_name: str | None = Field(None, max_length=120)
    contact_phone: str | None = Field(None, pattern=r"^1[3-9]\d{9}$")
    contact_email: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=2000)


class PartnerLawFirmUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    contact_name: str | None = Field(None, max_length=120)
    contact_phone: str | None = Field(None, pattern=r"^1[3-9]\d{9}$")
    contact_email: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=2000)
    is_active: bool | None = None


class PartnerLawFirmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    name: str
    contact_name: str | None = None
    contact_phone_masked: str | None = None
    contact_email: str | None = None
    seal_attachment_key: str | None = None
    notes: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ── InternalLegalLetterTemplate ────────────────────────────────
class LetterVariableSpec(BaseModel):
    name: str = Field(..., max_length=64, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    label: str = Field(..., max_length=120)
    type: Literal["string", "number", "date"] = "string"
    required: bool = True
    placeholder: str | None = Field(None, max_length=200)


class InternalLegalLetterTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: Literal["lawyer_letter", "notice", "reminder", "other"]
    body_md: str = Field(..., min_length=1, max_length=20000)
    variables: list[LetterVariableSpec] | None = None


class InternalLegalLetterTemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    category: Literal["lawyer_letter", "notice", "reminder", "other"] | None = None
    body_md: str | None = Field(None, min_length=1, max_length=20000)
    variables: list[LetterVariableSpec] | None = None
    is_active: bool | None = None


class InternalLegalLetterTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    name: str
    category: str
    body_md: str
    variables: list[dict[str, Any]] | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ── LegalInternalAction ────────────────────────────────────────
class LegalInternalActionCreate(BaseModel):
    action_type: ActionType
    note: str | None = Field(None, max_length=4000)
    letter_template_id: int | None = None
    partner_law_firm_id: int | None = None
    letter_variables: dict[str, Any] | None = None
    attachment_key: str | None = Field(None, max_length=512)
    attachment_filename: str | None = Field(None, max_length=255)


class LegalInternalActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    legal_order_id: int
    case_id: int
    action_type: str
    actor_user_id: int
    actor_name: str | None = None
    occurred_at: datetime
    note: str | None = None
    letter_template_id: int | None = None
    letter_template_name: str | None = None
    partner_law_firm_id: int | None = None
    partner_law_firm_name: str | None = None
    attachment_key: str | None = None
    attachment_filename: str | None = None
    letter_variables: dict[str, Any] | None = None


# ── LegalInternalOrder（视图，复用 LegalConversionOrder）────────
class LegalInternalOrderListItem(BaseModel):
    id: int
    case_id: int
    owner_name: str
    owner_phone_masked: str | None = None
    building: str | None = None
    room: str | None = None
    amount_owed: Decimal | None = None
    months_overdue: int | None = None
    status: str  # internal_processing / closed_* / escalated_to_lawfirm
    created_at: datetime
    requester_name: str | None = None
    last_action_at: datetime | None = None
    action_count: int = 0
    # v1.9.1 — closed_promised 时业主承诺缴清的日期；过期未付前端会标红
    promise_due_date: date | None = None
    # v1.9.7 — 列表行内项目上下文（用于「项目」列 + 按项目过滤）
    project_id: int | None = None
    project_name: str | None = None


class LegalInternalOrderDetailOut(BaseModel):
    id: int
    tenant_id: int
    case_id: int
    status: str
    owner_name: str
    owner_phone_masked: str | None = None
    building: str | None = None
    room: str | None = None
    amount_owed: Decimal | None = None
    months_overdue: int | None = None
    arrears_reason: str | None = None
    project_name: str | None = None
    notes: str | None = None
    created_at: datetime
    actions: list[LegalInternalActionOut]
    internal_close_reason: str | None = None
    internal_closed_at: datetime | None = None
    promise_due_date: date | None = None


class LegalInternalOrderCloseRequest(BaseModel):
    close_reason: CloseReason
    note: str | None = Field(None, max_length=2000)
    # v1.9.1 — close_reason='promised' 时填写业主承诺缴清的日期（必填）
    promise_due_date: date | None = None


class LegalInternalOrderReopenRequest(BaseModel):
    """v1.9.1 — 承诺到期未付时重新打开订单。"""
    note: str | None = Field(None, max_length=2000)


class LegalInternalOrderKpi(BaseModel):
    """v1.9.2 — 法务工作台 4 张 KPI 卡数据。"""
    pending_count: int = 0
    closed_this_month: int = 0
    avg_processing_days: float | None = None  # 本月已关闭订单的平均处理时长；无样本时 null
    escalation_rate_pct: float | None = None  # 本月（关闭+升级）里升级占比；无样本时 null
