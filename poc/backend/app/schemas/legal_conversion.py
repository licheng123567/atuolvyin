"""Sprint 16.1 — 法务转化通道 schema (PRD §20.4)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class LegalServicePackageOut(BaseModel):
    id: int
    slug: str
    package_type: str
    name: str
    description: str | None
    price: Decimal
    platform_fee_rate: Decimal
    enabled: bool
    sort_order: int

    model_config = {"from_attributes": True}


class ConvertCaseRequest(BaseModel):
    package_id: int = Field(..., gt=0)
    notes: str | None = Field(None, max_length=2000)


class LegalConversionOrderOut(BaseModel):
    id: int
    tenant_id: int
    case_id: int
    package_id: int
    package_name: str | None = None
    status: str
    price_quoted: Decimal
    platform_fee_amount: Decimal
    assigned_law_firm: str | None
    assigned_lawyer_name: str | None
    timeline_summary: dict[str, Any] | None
    recommendation: dict[str, Any] | None
    cost_estimate: dict[str, Any] | None
    notes: str | None
    created_by: int | None
    dispatched_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConvertCasePreviewOut(BaseModel):
    """Dry-run 预览：不创建订单，仅返回时间线 + 推荐 + 成本预估。"""
    timeline_summary: dict[str, Any]
    recommendation: dict[str, Any]
    available_packages: list[LegalServicePackageOut]


class DispatchOrderRequest(BaseModel):
    assigned_law_firm: str = Field(..., min_length=2, max_length=200)
    assigned_lawyer_name: str | None = Field(None, max_length=120)


class CompleteOrderRequest(BaseModel):
    notes: str | None = Field(None, max_length=2000)
