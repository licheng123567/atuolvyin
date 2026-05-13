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
    # v1.4 S16.4 — 直接 PATCH status='terminated' 已禁用，请走 terminate-request；
    # 仍允许 active <-> paused 互切。
    status: Literal["active", "paused"] | None = None


class TerminateRequestIn(BaseModel):
    """v1.4 S16.4 — 发起解约（D2 双向握手）。"""

    reason: str | None = Field(None, max_length=2000)


class TerminationStatusOut(BaseModel):
    """合同当前的解约握手状态（用于前端状态机）。"""

    contract_id: int
    status: str  # active / paused / terminated
    termination_requested_by: int | None  # 1=property, 2=provider
    termination_requested_at: datetime | None
    termination_reason: str | None
    termination_confirmed_at: datetime | None
    terminated_at: datetime | None
    timeout_days_remaining: int | None  # 7 天倒计时（请求未确认时）


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
