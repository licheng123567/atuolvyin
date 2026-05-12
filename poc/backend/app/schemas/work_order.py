"""Sprint 13 — Work Order schemas (workorder role)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WORK_ORDER_STATUSES = ("open", "in_progress", "resolved", "closed")
WORK_ORDER_TYPES = ("quality", "reduction", "dispute", "other")
WORK_ORDER_PRIORITIES = ("urgent_critical", "urgent", "normal", "low")

WorkOrderStatus = Literal["open", "in_progress", "resolved", "closed"]
WorkOrderType = Literal["quality", "reduction", "dispute", "other"]
WorkOrderPriority = Literal["urgent_critical", "urgent", "normal", "low"]


class WorkOrderCreate(BaseModel):
    order_type: WorkOrderType
    description: str = Field(..., min_length=1, max_length=4000)
    case_id: int | None = Field(None, gt=0)
    call_id: int | None = Field(None, gt=0)
    assigned_to: int | None = Field(None, gt=0)
    priority: WorkOrderPriority = "normal"

    model_config = ConfigDict(str_strip_whitespace=True)


class WorkOrderPatch(BaseModel):
    status: WorkOrderStatus | None = None
    assigned_to: int | None = Field(None, gt=0)
    resolution: str | None = Field(None, max_length=4000)
    description: str | None = Field(None, min_length=1, max_length=4000)
    priority: WorkOrderPriority | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class WorkOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    case_id: int | None
    call_id: int | None
    order_type: str
    description: str
    assigned_to: int | None
    status: str
    priority: str
    resolution: str | None
    created_at: datetime
    updated_at: datetime
    # enrichments
    assignee_name: str | None = None


class CaseRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stage: str
    owner_name: str
    owner_phone_masked: str


class CallRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime | None
    duration_sec: int | None
    result_tag: str | None


class WorkOrderDetailOut(WorkOrderOut):
    case: CaseRef | None = None
    call: CallRef | None = None


class WorkOrderKpi(BaseModel):
    """v1.9.6 — 工单工作台顶部 4 张 KPI 卡数据。"""
    open_count: int = 0
    in_progress_count: int = 0
    closed_this_month: int = 0  # resolved + closed 本月数量
    avg_processing_days: float | None = None
