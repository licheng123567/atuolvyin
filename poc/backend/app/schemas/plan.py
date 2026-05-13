"""Sprint 15 — PlanConfig CRUD schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlanConfigCreate(BaseModel):
    plan_name: str = Field(..., min_length=1, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=100)
    monthly_minutes: int = Field(..., ge=0, le=1_000_000)
    price_monthly: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("9999999.99"))
    features: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

    model_config = ConfigDict(str_strip_whitespace=True)


class PlanConfigPatch(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=100)
    monthly_minutes: int | None = Field(None, ge=0, le=1_000_000)
    price_monthly: Decimal | None = Field(None, ge=0, le=Decimal("9999999.99"))
    features: dict[str, Any] | None = None
    is_active: bool | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class PlanConfigActiveIn(BaseModel):
    is_active: bool


class PlanConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_name: str
    display_name: str
    monthly_minutes: int
    price_monthly: Decimal
    features: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
