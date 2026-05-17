"""§9.1 — 服务商法务端点 Pydantic schema。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.legal_conversion_request import LegalConversionRequestMaterialOut


class ProviderLegalCaseListItem(BaseModel):
    """服务商法务案件列表项。"""

    case_id: int
    owner_name: str | None = None
    owner_phone_masked: str | None = None
    building: str | None = None
    room: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    amount_owed: Decimal | None = None
    months_overdue: int | None = None
    stage: str


class ProviderLegalCaseDetail(BaseModel):
    """服务商法务案件详情（整理材料用）。"""

    case_id: int
    owner_name: str | None = None
    owner_phone_masked: str | None = None
    building: str | None = None
    room: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    pool_type: str
    stage: str
    status: str
    amount_owed: Decimal | None = None
    principal_amount: Decimal | None = None
    late_fee_amount: Decimal | None = None
    months_overdue: int | None = None
    arrears_reason: str | None = None
    last_contact_at: datetime | None = None
    monthly_contact_count: int
    priority_score: int
    call_count: int = 0
    last_call_at: datetime | None = None


class ProviderLegalConversionRequestCreate(BaseModel):
    """服务商法务发起法务转化请求入参。"""

    reason: str | None = Field(None, max_length=2000)


class ProviderLegalRequestOut(BaseModel):
    """服务商法务的法务转化请求 —— 列表项 / 创建结果。"""

    id: int
    tenant_id: int
    case_id: int
    owner_name: str | None = None
    project_id: int | None = None
    project_name: str | None = None
    amount_owed: Decimal | None = None
    reason: str | None = None
    status: str
    reviewer_note: str | None = None
    reviewed_at: datetime | None = None
    related_order_id: int | None = None
    order_status: str | None = None
    created_at: datetime
    updated_at: datetime


class ProviderLegalRequestDetail(ProviderLegalRequestOut):
    """请求详情 —— 在列表项基础上带补充材料列表。"""

    materials: list[LegalConversionRequestMaterialOut] = []
