"""Sprint 13 — Project Manager dashboard schemas."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TopOverdueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: int
    owner_name: str
    amount_owed: Decimal | None
    months_overdue: int | None
    stage: str


class PMPropertyStats(BaseModel):
    active_cases_count: int
    recovered_amount_month: float
    pending_workorders: int
    escalated_legal_cases: int
    agent_count: int
    top_overdue: list[TopOverdueItem]


class TopTenantItem(BaseModel):
    tenant_id: int
    tenant_name: str
    total_minutes: int
    contract_status: str | None


class PMProviderStats(BaseModel):
    active_contracts_count: int
    total_revenue_month: float
    agent_count: int
    pending_settlements: int
    top_tenants_by_volume: list[TopTenantItem]
