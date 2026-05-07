"""Sprint 11 — Service Provider schemas (platform_ops)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    provider_type: Literal["legal", "collection", "both"]
    admin_phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    contact_email: str | None = Field(None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$|^$")
    description: str | None = Field(None, max_length=2000)
    monthly_minute_quota: int | None = Field(None, ge=0, le=1000000)

    model_config = ConfigDict(str_strip_whitespace=True)


class ProviderPatch(BaseModel):
    """Partial update — name / description / contact_email / quota."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=2000)
    contact_email: str | None = Field(None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$|^$")
    monthly_minute_quota: int | None = Field(None, ge=0, le=1000000)

    model_config = ConfigDict(str_strip_whitespace=True)


class ProviderAuditIn(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _reject_requires_reason(self) -> ProviderAuditIn:
        if self.decision == "rejected" and not (self.reason and self.reason.strip()):
            raise ValueError("驳回必须填写原因")
        return self


class ProviderActiveIn(BaseModel):
    is_active: bool


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider_type: str
    admin_phone_masked: str
    contact_email: str | None
    description: str | None
    monthly_minute_quota: int | None
    is_active: bool
    audit_status: str
    audit_reason: str | None
    audit_at: datetime | None
    created_at: datetime
    # v1.4 — 推荐入驻溯源（仅 ops 视图）
    recommended_by_tenant_id: int | None = None
    recommended_by_tenant_name: str | None = None


class ProviderRecommendIn(BaseModel):
    """物业 admin 推荐服务商入驻（D1）。"""

    name: str = Field(..., min_length=1, max_length=100)
    provider_type: Literal["legal", "collection", "both"]
    admin_phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    contact_email: str | None = Field(
        None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$|^$"
    )
    description: str | None = Field(None, max_length=2000)

    model_config = ConfigDict(str_strip_whitespace=True)


class ProviderContractItem(BaseModel):
    """Contract row enriched with the partner tenant name."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    tenant_name: str
    signed_at: datetime
    expires_at: datetime | None
    service_types: list[str]
    status: str


class ProviderDetailOut(ProviderOut):
    contracts: list[ProviderContractItem]
