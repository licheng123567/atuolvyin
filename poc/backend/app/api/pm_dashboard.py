"""Sprint 13 — Project Manager dashboards.

GET /api/v1/pm/dashboard/property → PMPropertyStats
GET /api/v1/pm/dashboard/provider → PMProviderStats

property side queries against the user's tenant_id.
provider side queries against UserTenantMembership.provider_id.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.call import CallRecord
from app.models.case import CollectionCase, OwnerProfile
from app.models.settlement import SettlementStatement
from app.models.tenant import (
    ProviderTenantContract,
    Tenant,
    UserTenantMembership,
)
from app.models.user import UserAccount
from app.models.work import LegalCase, WorkOrder
from app.schemas.pm import (
    PMPropertyStats,
    PMProviderStats,
    TopOverdueItem,
    TopTenantItem,
)

router = APIRouter()

PROPERTY_PM_ROLES = ("project_manager_property", "admin")
PROVIDER_PM_ROLES = ("project_manager_provider",)


@router.get("/dashboard/property", response_model=PMPropertyStats)
async def get_property_pm_stats(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*PROPERTY_PM_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PMPropertyStats:
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        # Without a tenant we cannot scope; return empty stats rather than 500.
        return PMPropertyStats(
            active_cases_count=0,
            recovered_amount_month=0.0,
            pending_workorders=0,
            escalated_legal_cases=0,
            agent_count=0,
            top_overdue=[],
        )

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    active_cases_count: int = db.execute(
        select(func.count(CollectionCase.id)).where(
            CollectionCase.tenant_id == tenant_id,
            CollectionCase.status == "active",
        )
    ).scalar() or 0

    # "recovered_amount_month": sum of amount_owed for cases moved to "paid" this month.
    # Approximation — uses updated_at since we don't track stage transitions explicitly.
    recovered = db.execute(
        select(func.coalesce(func.sum(CollectionCase.amount_owed), 0)).where(
            CollectionCase.tenant_id == tenant_id,
            CollectionCase.stage == "paid",
            CollectionCase.updated_at >= month_start,
        )
    ).scalar() or 0
    recovered_amount_month = float(recovered)

    pending_workorders: int = db.execute(
        select(func.count(WorkOrder.id)).where(
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.status.in_(("open", "in_progress")),
        )
    ).scalar() or 0

    escalated_legal_cases: int = db.execute(
        select(func.count(LegalCase.id)).where(
            LegalCase.tenant_id == tenant_id,
            LegalCase.stage.notin_(("closed_won", "closed_lost", "closed_settled")),
        )
    ).scalar() or 0

    agent_count: int = db.execute(
        select(func.count(UserTenantMembership.id)).where(
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.role.in_(("agent_internal", "agent_external")),
            UserTenantMembership.is_active.is_(True),
        )
    ).scalar() or 0

    rows = db.execute(
        select(CollectionCase, OwnerProfile.name)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(
            CollectionCase.tenant_id == tenant_id,
            CollectionCase.status == "active",
        )
        .order_by(CollectionCase.amount_owed.desc().nulls_last())
        .limit(5)
    ).all()
    top_overdue = [
        TopOverdueItem(
            case_id=cc.id,
            owner_name=name,
            amount_owed=cc.amount_owed,
            months_overdue=cc.months_overdue,
            stage=cc.stage,
        )
        for cc, name in rows
    ]

    return PMPropertyStats(
        active_cases_count=active_cases_count,
        recovered_amount_month=recovered_amount_month,
        pending_workorders=pending_workorders,
        escalated_legal_cases=escalated_legal_cases,
        agent_count=agent_count,
        top_overdue=top_overdue,
    )


@router.get("/dashboard/provider", response_model=PMProviderStats)
async def get_provider_pm_stats(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*PROVIDER_PM_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PMProviderStats:
    user_id: int | None = payload.get("user_id")
    provider_id: int | None = None

    if user_id:
        membership = db.execute(
            select(UserTenantMembership)
            .where(
                UserTenantMembership.user_id == user_id,
                UserTenantMembership.is_active.is_(True),
                UserTenantMembership.provider_id.is_not(None),
            )
            .limit(1)
        ).scalar_one_or_none()
        if membership is not None:
            provider_id = membership.provider_id

    if provider_id is None:
        return PMProviderStats(
            active_contracts_count=0,
            total_revenue_month=0.0,
            agent_count=0,
            pending_settlements=0,
            top_tenants_by_volume=[],
        )

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = month_start + timedelta(days=32)
    month_end = month_end.replace(day=1)

    active_contracts_count: int = db.execute(
        select(func.count(ProviderTenantContract.id)).where(
            ProviderTenantContract.provider_id == provider_id,
            ProviderTenantContract.status == "active",
        )
    ).scalar() or 0

    # total_revenue_month: sum of settlement_statement.total_amount where contract belongs
    # to provider and period overlaps current month
    revenue = db.execute(
        select(func.coalesce(func.sum(SettlementStatement.total_amount), 0))
        .join(
            ProviderTenantContract,
            ProviderTenantContract.id == SettlementStatement.contract_id,
        )
        .where(
            ProviderTenantContract.provider_id == provider_id,
            SettlementStatement.period_start >= month_start,
            SettlementStatement.period_start < month_end,
        )
    ).scalar() or 0
    total_revenue_month = float(revenue)

    agent_count: int = db.execute(
        select(func.count(UserTenantMembership.id)).where(
            UserTenantMembership.provider_id == provider_id,
            UserTenantMembership.role.in_(("agent_internal", "agent_external")),
            UserTenantMembership.is_active.is_(True),
        )
    ).scalar() or 0

    pending_settlements: int = db.execute(
        select(func.count(SettlementStatement.id))
        .join(
            ProviderTenantContract,
            ProviderTenantContract.id == SettlementStatement.contract_id,
        )
        .where(
            ProviderTenantContract.provider_id == provider_id,
            SettlementStatement.status.in_(("DRAFT", "CONFIRMED", "DISPUTED")),
        )
    ).scalar() or 0

    # top tenants by call volume
    rows = db.execute(
        select(
            Tenant.id,
            Tenant.name,
            func.coalesce(func.count(CallRecord.id), 0).label("call_count"),
            ProviderTenantContract.status,
        )
        .join(
            ProviderTenantContract,
            ProviderTenantContract.tenant_id == Tenant.id,
        )
        .outerjoin(CallRecord, CallRecord.tenant_id == Tenant.id)
        .where(ProviderTenantContract.provider_id == provider_id)
        .group_by(Tenant.id, Tenant.name, ProviderTenantContract.status)
        .order_by(func.count(CallRecord.id).desc())
        .limit(5)
    ).all()
    top_tenants = [
        TopTenantItem(
            tenant_id=tid,
            tenant_name=tname,
            total_minutes=int(cnt),
            contract_status=cstatus,
        )
        for tid, tname, cnt, cstatus in rows
    ]

    return PMProviderStats(
        active_contracts_count=active_contracts_count,
        total_revenue_month=total_revenue_month,
        agent_count=agent_count,
        pending_settlements=pending_settlements,
        top_tenants_by_volume=top_tenants,
    )
