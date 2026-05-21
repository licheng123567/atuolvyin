"""v0.6.0 — 培训案例库 schemas。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TrainingCategory = Literal["negotiate", "escalate", "objection", "investigate"]
TrainingSource = Literal["auto", "manual"]


class TrainingCaseOut(BaseModel):
    """列表 / 详情响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    title: str
    category: TrainingCategory
    scenario: str
    lesson: str
    raw_call_id: int | None
    raw_risk_event_id: int | None
    source: TrainingSource
    created_by: int | None
    created_by_name: str | None = None  # 由 API 补齐
    rating: int
    views: int
    created_at: datetime
    updated_at: datetime


class TrainingCaseCreateIn(BaseModel):
    """督导手工录入(POST /supervisor/training-cases)。"""

    title: str = Field(..., min_length=2, max_length=256)
    category: TrainingCategory
    scenario: str = Field(..., min_length=1, max_length=4000)
    lesson: str = Field(..., min_length=1, max_length=4000)
    raw_call_id: int | None = None
    rating: int = Field(default=0, ge=0, le=5)


class TrainingCaseListResp(BaseModel):
    items: list[TrainingCaseOut]
    total: int
