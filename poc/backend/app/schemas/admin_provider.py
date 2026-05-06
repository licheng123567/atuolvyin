"""Sprint 8 — Admin (物业管理员) view of partner Service Providers.

物业管理员管理本公司与服务商的签约关系：
- 列出签约服务商
- 邀请已审核服务商建立合作（创建 ProviderTenantContract）
- 查看该服务商在本公司的成员配置
- 调整合同（到期日 / 服务类型 / 状态）与成员配额
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AdminProviderListItem(BaseModel):
    """A signed provider as seen from the property admin's tenant."""

    provider_id: int
    provider_name: str
    provider_type: str
    contract_id: int
    signed_at: datetime
    expires_at: datetime | None
    service_types: list[str]
    status: str
    member_count: int


class AdminAvailableProviderItem(BaseModel):
    """An approved provider the tenant can invite (no active contract yet)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider_type: str
    description: str | None
    contact_email: str | None


class AdminProviderInviteIn(BaseModel):
    provider_id: int
    service_types: list[str] = Field(..., min_length=1)
    expires_at: datetime | None = None


class AdminProviderContractOut(BaseModel):
    contract_id: int
    provider_id: int
    provider_name: str
    signed_at: datetime
    expires_at: datetime | None
    service_types: list[str]
    status: str


class AdminProviderContractPatchIn(BaseModel):
    expires_at: datetime | None = None
    service_types: list[str] | None = Field(None, min_length=1)
    status: Literal["active", "paused", "terminated"] | None = None


class AdminProviderMemberOut(BaseModel):
    user_id: int
    name: str
    phone_masked: str
    role: str
    quota: int | None
    expire_at: datetime | None
    access_hours: str | None
    is_active: bool


class AdminProviderMemberPatchIn(BaseModel):
    quota: int | None = Field(None, ge=0, le=1_000_000)
    expire_at: datetime | None = None
    access_hours: str | None = Field(None, max_length=50)
    is_active: bool | None = None
