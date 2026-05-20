"""v1.6.8 — 法务转化申请审批 schema."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class LegalConversionRequestOut(BaseModel):
    """审批 inbox 列表项 + 详情。已含 case + requester 简要快照。"""

    id: int
    tenant_id: int
    case_id: int
    # case 简要快照
    owner_name: str | None = None
    owner_phone_masked: str | None = None
    building: str | None = None
    room: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    amount_owed: Decimal | None = None
    months_overdue: int | None = None
    case_stage: str | None = None
    # 申请人
    requester_user_id: int
    requester_role: str
    requester_name: str | None = None
    reason: str | None = None
    # 状态
    status: str  # 'pending' | 'approved' | 'rejected' | 'cancelled'
    reviewer_user_id: int | None = None
    reviewer_role: str | None = None
    reviewer_name: str | None = None
    reviewed_at: datetime | None = None
    reviewer_note: str | None = None
    related_order_id: int | None = None
    # 时间
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApproveLegalConversionRequestBody(BaseModel):
    """督导/admin 批准转法务申请。

    v0.5.4 起,批准 = 仅同意「转出案件」,**不**选服务包(服务包改由法务在
    /legal-finalize 端点接单时选择)。请求体可选填 notes 给法务参考。
    package_id 字段保留(向后兼容旧客户端),但已不再使用 —— 服务端会忽略。
    """

    package_id: int | None = Field(None, gt=0, description="DEPRECATED v0.5.4 — 服务端忽略;由法务接单时选包")
    notes: str | None = Field(None, max_length=2000)


class FinalizeLegalConversionRequestBody(BaseModel):
    """v0.5.4 — 法务接单选服务包,把 approved_pending_legal 请求转为 approved + 建 Order。"""

    package_id: int = Field(..., gt=0)
    notes: str | None = Field(None, max_length=2000)


class RejectLegalConversionRequestBody(BaseModel):
    """督导/admin 驳回申请：必填驳回理由。"""

    reason: str = Field(..., min_length=1, max_length=2000)


class LegalConversionRequestMaterialOut(BaseModel):
    """法务转化请求的补充材料元数据。"""

    id: int
    request_id: int
    filename: str
    content_type: str | None = None
    size_bytes: int | None = None
    uploaded_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


class LegalConversionRequestMaterialDownloadOut(BaseModel):
    """补充材料下载链接。"""

    download_url: str
    filename: str
    content_type: str | None = None
    size_bytes: int | None = None
    expires_in_sec: int = 3600


class LegalConversionRequestDetailOut(LegalConversionRequestOut):
    """物业审批人看到的请求详情 —— 在 inbox 列表项基础上带补充材料 + 订单高阶状态。"""

    order_status: str | None = None
    materials: list[LegalConversionRequestMaterialOut] = []
