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
