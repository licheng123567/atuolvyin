from datetime import date, datetime
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
    # v1.6.3 — 账单字段（导入时直接录入，不再按月推算明细）
    bill_period_start: date | None = None
    bill_period_end: date | None = None
    principal_amount: Decimal | None = None  # 物业费
    late_fee_amount: Decimal | None = None  # 违约金 / 滞纳金
    arrears_reason: str | None = None  # 经济困难 / 服务质量异议 / 房屋空置 / 租客拖欠 / 其他
    notes: str | None = None  # 欠费情况说明（拒缴/暂时困难/失联等）


class OwnerInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str | None = None  # decrypted, only for agent_internal
    phone_masked: str
    building: str | None
    room: str | None
    do_not_call: bool


class CaseWithOwnerResponse(BaseModel):
    id: int
    tenant_id: int
    project_id: int | None
    project_name: str | None = None
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
    # v1.5.5 — 项目所属服务商（无项目 / 物业自办时为 None）
    provider_id: int | None = None
    provider_name: str | None = None


class CaseImportRequest(BaseModel):
    project_id: int | None = None
    rows: list[CaseImportRow] = Field(..., min_length=1, max_length=500)


class CaseImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


class CaseStageUpdate(BaseModel):
    stage: Literal["new", "in_progress", "promised", "paid", "escalated", "closed"]
    note: str | None = None  # v1.6.6 — 阶段变更跟进备注（写入 audit log）


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
    recording_url: str | None = None  # v1.6.7 — E5 inline 录音播放


class TimelineEvent(BaseModel):
    type: str
    ts: datetime
    actor: str | None
    note: str | None
    # v1.6.9 — 关联实体 ID，让前端能跳到对应详情页（工单/法务订单/通话）
    target_id: int | None = None
    # 'workorder' / 'legal_order' / 'legal_case' / 'call' / 'audit'
    target_type: str | None = None


class CaseProjectInfo(BaseModel):
    """v1.6.3 — 案件详情中嵌入项目基本信息（合同 + 收费），无需另起接口。"""

    name: str
    charge_rate_text: str | None = None
    charge_period: str | None = None
    contract_type: str | None = None
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    contract_attachment_key: str | None = None
    contract_attachment_filename: str | None = None
    charge_notes: str | None = None


class CaseDetailResponse(BaseModel):
    id: int
    tenant_id: int
    project_id: int | None
    project_name: str | None = None
    project_info: CaseProjectInfo | None = None  # v1.6.3
    owner: OwnerInfo
    assigned_to: int | None
    assigned_role: str | None = (
        None  # v1.4 — 协作来源 badge：agent_internal / agent_external / null
    )
    pool_type: str
    stage: str
    amount_owed: Decimal | None
    months_overdue: int | None
    # v1.6.3 — 账单字段（导入时录入，不再按月推算）
    bill_period_start: date | None = None
    bill_period_end: date | None = None
    principal_amount: Decimal | None = None
    late_fee_amount: Decimal | None = None
    arrears_reason: str | None = None
    priority_score: int
    last_contact_at: datetime | None
    monthly_contact_count: int
    # v1.8.0 — 业主画像 3 统计卡片：联系次数复用 monthly_contact_count
    promise_count: int = 0
    workorder_count: int = 0
    status: str
    created_at: datetime
    updated_at: datetime
    calls: list[CaseCallItem]
    timeline_events: list[TimelineEvent]
    # v1.5 — 服务团队（电话团队 = 项目签约的服务商；法务团队 = 转化订单已撮合的律所）
    calling_provider_id: int | None = None
    calling_provider_name: str | None = None
    legal_law_firm_name: str | None = None
    legal_lawyer_name: str | None = None
    legal_order_status: str | None = None
