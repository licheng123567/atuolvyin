from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    credit_code: Optional[str] = Field(None, max_length=50)
    admin_phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    plan: Literal["trial", "standard", "premium"] = "trial"
    monthly_minute_quota: Optional[int] = Field(None, ge=0, le=100000)

    model_config = ConfigDict(str_strip_whitespace=True)


class TenantQuotaUpdate(BaseModel):
    monthly_minute_quota: int = Field(..., ge=0, le=100000)


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    credit_code: Optional[str]
    admin_phone_masked: str  # computed by service layer
    plan: str
    monthly_minute_quota: Optional[int]
    expires_at: Optional[datetime]
    is_active: bool
    created_at: datetime
