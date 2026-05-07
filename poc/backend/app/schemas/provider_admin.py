"""Sprint 14 — provider_admin schemas.

Schemas for the service provider's own admin user (provider_admin role).
Pages: PA.3.1 总览 / PA.3.2 合作租户 / PA.3.3 团队管理 / PA.3.4 收入数据.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.settlement import DisputeOut, SettlementStatus

# ── Dashboard (PA.3.1) ──────────────────────────────────────────────────


class ProviderContractSummary(BaseModel):
    """Contract row used inside the provider dashboard summary."""

    model_config = ConfigDict(from_attributes=True)

    tenant_id: int
    tenant_name: str
    status: str
    signed_at: datetime
    expires_at: datetime | None = None


class ProviderDashboardStats(BaseModel):
    provider_name: str
    partner_tenant_count: int
    team_count: int
    revenue_month: Decimal
    pending_settlement_total: Decimal
    contracts: list[ProviderContractSummary]


# ── Partner tenants (PA.3.2) ────────────────────────────────────────────


class ProviderTenantOut(BaseModel):
    """A row in /provider/tenants — a tenant this provider has signed with."""

    model_config = ConfigDict(from_attributes=True)

    tenant_id: int
    name: str
    contract_id: int
    signed_at: datetime
    expires_at: datetime | None = None
    status: str
    service_types: list[str]


# ── Team management (PA.3.3) ────────────────────────────────────────────


class ProviderTeamMemberOut(BaseModel):
    """Provider staff team member."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    name: str
    phone_masked: str
    role: str
    is_active: bool
    created_at: datetime


class ProviderTeamMemberDetailOut(ProviderTeamMemberOut):
    """Detail variant — currently same shape; reserved for future fields."""


class TeamActiveIn(BaseModel):
    is_active: bool


class TeamMemberCreateIn(BaseModel):
    """Provider creates a new team member (catcher / supervisor / external).

    `tenant_id` is required so the membership row has a tenant scope —
    a provider may serve multiple tenants, so they pick which tenant
    the new member is assigned to (must be a tenant the provider has
    an active contract with).
    """

    name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    password: str = Field(..., min_length=8, max_length=72)
    role: str = Field(
        ...,
        pattern=r"^(supervisor|agent_internal|agent_external)$",
    )
    tenant_id: int


# ── Settlements (PA.3.4) — read-only ────────────────────────────────────


class ProviderSettlementOut(BaseModel):
    """List item for /provider/settlements."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    tenant_id: int
    tenant_name: str
    period_start: datetime
    period_end: datetime
    total_amount: Decimal
    status: SettlementStatus
    payment_proof_url: str | None = None
    confirmed_at: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProviderSettlementDetailOut(ProviderSettlementOut):
    disputes: list[DisputeOut] = Field(default_factory=list)


# ── Sprint 9.1 — cross-tenant team performance ──────────────────────────


class ProviderMemberPerformance(BaseModel):
    user_id: int
    name: str
    role: str
    total_calls: int
    connected_calls: int
    promised_cases: int
    conversion_rate: float | None
    paid_amount: Decimal


# ── Sprint 9.2 — single-member commission breakdown ─────────────────────


class CommissionLineItem(BaseModel):
    case_id: int
    owner_name: str
    paid_amount: Decimal
    paid_at: datetime | None


class ProviderMemberCommission(BaseModel):
    user_id: int
    name: str
    year_month: str
    commission_rate: float  # e.g. 0.05 = 5%
    base_amount: Decimal  # sum of paid amounts for this user / month
    commission: Decimal  # base_amount * rate
    items: list[CommissionLineItem]


# ── Sprint 9.3 — dispute submission ─────────────────────────────────────


class ProviderDisputeIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class ProviderDisputeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    statement_id: int
    reason: str
    status: str  # open / resolved / rejected
    resolution: str | None
    submitted_by: int
    created_at: datetime
