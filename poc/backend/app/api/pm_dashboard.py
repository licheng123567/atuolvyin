"""Sprint 13 — Project Manager dashboards.

GET /api/v1/pm/dashboard/property → PMPropertyStats
GET /api/v1/pm/dashboard/provider → PMProviderStats

property side queries against the user's tenant_id.
provider side queries against UserTenantMembership.provider_id.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import (
    get_token_payload,
    require_provider_roles,
    require_roles,
    require_tenant_roles,
)
from app.models.call import CallRecord
from app.models.case import CollectionCase, OwnerProfile, Project
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

PROPERTY_PM_ROLES = ("project_manager", "admin")
PROVIDER_PM_ROLES = ("project_manager",)


@router.get("/dashboard/property", response_model=PMPropertyStats)
async def get_property_pm_stats(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*PROPERTY_PM_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PMPropertyStats:
    # Guard: provider-side callers (provider_id is not None in JWT) must not
    # receive property-side data.  Mirror the symmetric guard in
    # get_provider_pm_stats, which returns empty stats for property-side callers.
    if payload.get("provider_id") is not None:
        return PMPropertyStats(
            active_cases_count=0,
            recovered_amount_month=0.0,
            pending_workorders=0,
            escalated_legal_cases=0,
            agent_count=0,
            top_overdue=[],
        )

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

    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    active_cases_count: int = (
        db.execute(
            select(func.count(CollectionCase.id)).where(
                CollectionCase.tenant_id == tenant_id,
                CollectionCase.status == "active",
            )
        ).scalar()
        or 0
    )

    # "recovered_amount_month": sum of amount_owed for cases moved to "paid" this month.
    # Approximation — uses updated_at since we don't track stage transitions explicitly.
    recovered = (
        db.execute(
            select(func.coalesce(func.sum(CollectionCase.amount_owed), 0)).where(
                CollectionCase.tenant_id == tenant_id,
                CollectionCase.stage == "paid",
                CollectionCase.updated_at >= month_start,
            )
        ).scalar()
        or 0
    )
    recovered_amount_month = float(recovered)

    pending_workorders: int = (
        db.execute(
            select(func.count(WorkOrder.id)).where(
                WorkOrder.tenant_id == tenant_id,
                WorkOrder.status.in_(("open", "in_progress")),
            )
        ).scalar()
        or 0
    )

    escalated_legal_cases: int = (
        db.execute(
            select(func.count(LegalCase.id)).where(
                LegalCase.tenant_id == tenant_id,
                LegalCase.stage.notin_(("closed_won", "closed_lost", "closed_settled")),
            )
        ).scalar()
        or 0
    )

    agent_count: int = (
        db.execute(
            select(func.count(UserTenantMembership.id)).where(
                UserTenantMembership.tenant_id == tenant_id,
                UserTenantMembership.role == "agent",
                UserTenantMembership.is_active.is_(True),
            )
        ).scalar()
        or 0
    )

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
    _user: Annotated[UserAccount, Depends(require_provider_roles(*PROVIDER_PM_ROLES))],
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

    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = month_start + timedelta(days=32)
    month_end = month_end.replace(day=1)

    active_contracts_count: int = (
        db.execute(
            select(func.count(ProviderTenantContract.id)).where(
                ProviderTenantContract.provider_id == provider_id,
                ProviderTenantContract.status == "active",
            )
        ).scalar()
        or 0
    )

    # total_revenue_month: sum of settlement_statement.total_amount where contract belongs
    # to provider and period overlaps current month
    revenue = (
        db.execute(
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
        ).scalar()
        or 0
    )
    total_revenue_month = float(revenue)

    agent_count: int = (
        db.execute(
            select(func.count(UserTenantMembership.id)).where(
                UserTenantMembership.provider_id == provider_id,
                UserTenantMembership.role == "agent",
                UserTenantMembership.is_active.is_(True),
            )
        ).scalar()
        or 0
    )

    pending_settlements: int = (
        db.execute(
            select(func.count(SettlementStatement.id))
            .join(
                ProviderTenantContract,
                ProviderTenantContract.id == SettlementStatement.contract_id,
            )
            .where(
                ProviderTenantContract.provider_id == provider_id,
                SettlementStatement.status.in_(("DRAFT", "CONFIRMED", "DISPUTED")),
            )
        ).scalar()
        or 0
    )

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


# ── v1.4 — PM 管理多项目 ──────────────────────────────────


from pydantic import BaseModel  # noqa: E402


class PmProjectCard(BaseModel):
    project_id: int
    project_name: str
    role_in_project: str  # "property_pm" / "provider_pm"
    case_count: int
    receivable: float
    received: float
    promised_count: int
    new_count: int
    in_progress_count: int
    escalated_count: int
    provider_name: str | None
    allow_internal_assist: bool


@router.get("/projects", response_model=list[PmProjectCard])
async def list_my_projects(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[
        UserAccount,
        Depends(require_roles("project_manager")),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> list[PmProjectCard]:
    """返回当前 PM 管理的所有项目（卡片列表）。一人多项目场景。

    property vs provider 由 provider_id 区分：
      - provider_id is None  → 物业侧 PM（看 property_pm_user_id）
      - provider_id is not None → 服务商侧 PM（看 provider_pm_user_id，仅 active 项目）
    """
    user_id = int(payload.get("user_id") or 0)
    provider_id = payload.get("provider_id")  # None = property side, int = provider side

    if provider_id is None:
        # 物业侧 PM
        role_in_project_label = "property_pm"
        rows = (
            db.execute(
                select(Project)
                .where(Project.property_pm_user_id == user_id)
                .order_by(Project.id.desc())
            )
            .scalars()
            .all()
        )
    else:
        # 服务商侧 PM — v1.5.5 仅看 active + 服务期未过的项目
        from sqlalchemy import or_

        role_in_project_label = "provider_pm"
        rows = (
            db.execute(
                select(Project)
                .where(
                    Project.provider_pm_user_id == user_id,
                    Project.status == "active",
                    or_(Project.plan_end.is_(None), Project.plan_end >= func.now()),
                )
                .order_by(Project.id.desc())
            )
            .scalars()
            .all()
        )
    # role is "project_manager" for both sides; distinction is via provider_id

    cards: list[PmProjectCard] = []
    for p in rows:
        case_data = db.execute(
            select(CollectionCase.stage, CollectionCase.amount_owed).where(
                CollectionCase.project_id == p.id,
                CollectionCase.tenant_id == p.tenant_id,
            )
        ).all()
        receivable = 0.0
        received = 0.0
        promised = new_c = in_progress = escalated = 0
        for stage, amt in case_data:
            f = float(amt or 0)
            receivable += f
            if stage == "paid":
                received += f
            elif stage == "promised":
                promised += 1
            elif stage == "new":
                new_c += 1
            elif stage == "in_progress":
                in_progress += 1
            elif stage == "escalated":
                escalated += 1

        provider_name = None
        if p.provider_id:
            from app.models.tenant import ServiceProvider

            provider_name = db.execute(
                select(ServiceProvider.name).where(ServiceProvider.id == p.provider_id)
            ).scalar_one_or_none()

        cards.append(
            PmProjectCard(
                project_id=p.id,
                project_name=p.name,
                role_in_project=role_in_project_label,
                case_count=len(case_data),
                receivable=round(receivable, 2),
                received=round(received, 2),
                promised_count=promised,
                new_count=new_c,
                in_progress_count=in_progress,
                escalated_count=escalated,
                provider_name=provider_name,
                allow_internal_assist=p.allow_internal_assist,
            )
        )
    return cards


# ── v0.6.0 — PM dashboard 运营提醒(5 类) ─────────────────────────
from pydantic import BaseModel  # noqa: E402


class PMAlertCard(BaseModel):
    """运营提醒卡片(纯数字 + 跳转链接)。"""

    key: str  # pending_approval_backlog / promise_overdue_uncalled / agent_anomaly / cost_warning / case_stage_stuck
    label: str  # UI 显示标签
    count: int  # 数字
    severity: str  # info / warn / critical
    detail_path: str | None  # 前端跳转路径(查看详情)


class PMAlertsOut(BaseModel):
    scope: str  # property / provider
    alerts: list[PMAlertCard]


@router.get("/dashboard/alerts", response_model=PMAlertsOut)
async def get_pm_alerts(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles("project_manager", "admin"))],
    db: Annotated[Session, Depends(get_db)],
) -> PMAlertsOut:
    """PM dashboard 顶部运营提醒卡片网格 — 5 类提醒数字 + 跳转链接。

    五类:
      1. pending_approval_backlog:> 3 天的减免申请 + 转法务申请积压
      2. promise_overdue_uncalled:承诺已逾期但本租户最近 3 天无 urge 动作
      3. agent_anomaly:近 7 天连续 5 通无接 / 缺勤的催收员数
      4. cost_warning:本月分钟消费超预算 80% 的项目数(简化:超 2000 分钟即告警)
      5. case_stage_stuck:某 stage 停留 > 14 天的案件数

    物业 PM (provider_id IS NULL):全租户视角
    服务商 PM (provider_id IS NOT NULL):限本服务商接的项目
    """
    from app.models.discount_offer import DiscountOffer
    from app.models.legal_conversion import LegalConversionRequest
    from app.models.tenant import TenantMinuteUsage

    tenant_id = payload.get("tenant_id")
    provider_id = payload.get("provider_id")
    is_provider = provider_id is not None
    scope = "provider" if is_provider else "property"

    if not tenant_id and not is_provider:
        return PMAlertsOut(scope=scope, alerts=[])

    now = datetime.now(UTC)
    three_days_ago = now - timedelta(days=3)
    fourteen_days_ago = now - timedelta(days=14)
    seven_days_ago = now - timedelta(days=7)
    year_month = now.strftime("%Y-%m")

    # 1. 审批积压 — > 3 天的 pending discount/legal 申请
    discount_backlog = (
        db.execute(
            select(func.count(DiscountOffer.id))
            .where(DiscountOffer.tenant_id == tenant_id)
            .where(DiscountOffer.status.in_(("pending_supervisor", "pending_admin")))
            .where(DiscountOffer.created_at < three_days_ago)
        ).scalar()
        or 0
    )
    legal_req_backlog = (
        db.execute(
            select(func.count(LegalConversionRequest.id))
            .where(LegalConversionRequest.tenant_id == tenant_id)
            .where(LegalConversionRequest.status.in_(("pending", "pending_admin")))
            .where(LegalConversionRequest.created_at < three_days_ago)
        ).scalar()
        or 0
    )
    approval_backlog = int(discount_backlog) + int(legal_req_backlog)

    # 2. 承诺已逾期 + 近 3 天无 urge 动作的案件
    # 简化:统计 promise_due_at < now - 1 day 且 stage != 'paid' 的案件
    promise_overdue = (
        db.execute(
            select(func.count(CollectionCase.id))
            .where(CollectionCase.tenant_id == tenant_id)
            .where(CollectionCase.promise_due_at.isnot(None))
            .where(CollectionCase.promise_due_at < now - timedelta(days=1))
            .where(CollectionCase.stage != "paid")
        ).scalar()
        or 0
    )

    # 3. 坐席异常 — 近 7 天无任何 CallRecord 的催收员数(本租户)
    active_agent_ids = (
        db.execute(
            select(UserTenantMembership.user_id)
            .where(UserTenantMembership.tenant_id == tenant_id)
            .where(UserTenantMembership.role == "agent")
            .where(UserTenantMembership.is_active.is_(True))
        )
        .scalars()
        .all()
    )

    if active_agent_ids:
        agents_with_calls = (
            db.execute(
                select(func.count(func.distinct(CallRecord.caller_user_id)))
                .where(CallRecord.tenant_id == tenant_id)
                .where(CallRecord.caller_user_id.in_(active_agent_ids))
                .where(CallRecord.created_at >= seven_days_ago)
            ).scalar()
            or 0
        )
        agent_anomaly = max(0, len(active_agent_ids) - int(agents_with_calls))
    else:
        agent_anomaly = 0

    # 4. 成本预警 — 本月分钟用量 > 2000 的租户/项目数(简化逻辑)
    cost_row = db.execute(
        select(TenantMinuteUsage.used_minutes)
        .where(TenantMinuteUsage.tenant_id == tenant_id)
        .where(TenantMinuteUsage.year_month == year_month)
    ).scalar_one_or_none()
    cost_warning = 1 if cost_row and int(cost_row) > 2000 else 0

    # 5. 案件 stage 停留 > 14 天(updated_at 计算)
    stage_stuck = (
        db.execute(
            select(func.count(CollectionCase.id))
            .where(CollectionCase.tenant_id == tenant_id)
            .where(CollectionCase.updated_at < fourteen_days_ago)
            .where(CollectionCase.stage.in_(("new", "in_progress", "promised", "escalated")))
        ).scalar()
        or 0
    )

    alerts = [
        PMAlertCard(
            key="pending_approval_backlog",
            label="审批积压(>3 天)",
            count=approval_backlog,
            severity="warn" if approval_backlog > 0 else "info",
            detail_path="/admin/discount-approvals" if not is_provider else None,
        ),
        PMAlertCard(
            key="promise_overdue_uncalled",
            label="承诺逾期未催",
            count=int(promise_overdue),
            severity="critical"
            if promise_overdue > 5
            else "warn"
            if promise_overdue > 0
            else "info",
            detail_path="/supervisor/promises",
        ),
        PMAlertCard(
            key="agent_anomaly",
            label="坐席异常(7 天无通话)",
            count=int(agent_anomaly),
            severity="warn" if agent_anomaly > 0 else "info",
            detail_path="/admin/agent-devices" if not is_provider else "/provider/team",
        ),
        PMAlertCard(
            key="cost_warning",
            label="本月分钟超 2000",
            count=int(cost_warning),
            severity="warn" if cost_warning else "info",
            detail_path="/admin/billing/minute-usage"
            if not is_provider
            else "/provider/billing/minute-usage",
        ),
        PMAlertCard(
            key="case_stage_stuck",
            label="案件阶段停留 >14 天",
            count=int(stage_stuck),
            severity="critical" if stage_stuck > 50 else "warn" if stage_stuck > 0 else "info",
            detail_path="/admin/cases" if not is_provider else "/provider/cases",
        ),
    ]
    return PMAlertsOut(scope=scope, alerts=alerts)
