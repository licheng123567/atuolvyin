from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.call import (
    AnalysisResult,
    CallRecord,
    RiskEvent,
    SuggestionFeedback,
)
from app.models.case import CollectionCase, Project
from app.models.audit import PlanConfig
from app.models.tenant import (
    ServiceProvider,
    Tenant,
    TenantMinuteUsage,
    UserTenantMembership,
)
from app.models.user import UserAccount
from app.schemas.dashboard import (
    AdminDashboardStats,
    AgentRanking,
    ProjectKpi,
    ProviderKpi,
    QuotaStats,
    TodayStats,
)

router = APIRouter()

# supervisor 也能看（PRD 4.1 督导工作台首页有部分相同 KPI）
ADMIN_ROLES = ("admin", "supervisor")

# Intent values that count as "promise to pay"
_PROMISE_INTENTS = ("承诺缴", "promise_made", "promised")


@router.get("/dashboard/stats", response_model=AdminDashboardStats)
def get_dashboard_stats(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> AdminDashboardStats:
    tenant_id = int(payload.get("tenant_id") or 0)

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    seven_days_ago = today_start - timedelta(days=7)
    month_start = today_start.replace(day=1)

    # ── 1. Today stats ────────────────────────────────────────────────────────

    # Total outbound calls today
    outbound_count: int = db.execute(
        select(func.count(CallRecord.id)).where(
            CallRecord.tenant_id == tenant_id,
            CallRecord.started_at >= today_start,
            CallRecord.started_at < today_end,
        )
    ).scalar() or 0

    # Connected = duration_sec > 10
    connected_count: int = db.execute(
        select(func.count(CallRecord.id)).where(
            CallRecord.tenant_id == tenant_id,
            CallRecord.started_at >= today_start,
            CallRecord.started_at < today_end,
            CallRecord.duration_sec > 10,
        )
    ).scalar() or 0

    # Promised: AnalysisResult.key_segments['intent'] in PROMISE_INTENTS
    # key_segments is a JSON column — use PostgreSQL ->> operator via sa.type_coerce / cast
    promised_count = _count_promised(db, tenant_id, today_start, today_end)

    # 今日承诺缴金额合计：今日 promise 通话所属 case 的 amount_owed 累计
    # （MVP 没有独立回款流水表；schema 标注语义为「今日承诺缴金额」）
    recovered_amount = _sum_promised_amount(db, tenant_id, today_start, today_end)

    # ── 2. Quota ──────────────────────────────────────────────────────────────

    tenant = db.get(Tenant, tenant_id)
    year_month = now.strftime("%Y-%m")
    usage = db.execute(
        select(TenantMinuteUsage).where(
            TenantMinuteUsage.tenant_id == tenant_id,
            TenantMinuteUsage.year_month == year_month,
        )
    ).scalar_one_or_none()

    used_min: int = usage.used_minutes if usage else 0
    realtime_min: int = usage.realtime_minutes if usage else 0
    post_min: int = usage.post_minutes if usage else 0
    total_min: int | None = tenant.monthly_minute_quota if tenant else None
    remaining_min: int | None = (
        (total_min - used_min) if total_min is not None else None
    )
    warning: bool = bool(total_min and used_min >= total_min * 0.8)

    # Sprint 14.1 — 套餐细分配额（PlanConfig.monthly_realtime/post_minutes）
    realtime_quota: int | None = None
    post_quota: int | None = None
    if tenant and tenant.plan:
        plan = db.execute(
            select(PlanConfig).where(PlanConfig.plan_name == tenant.plan)
        ).scalar_one_or_none()
        if plan:
            realtime_quota = plan.monthly_realtime_minutes
            post_quota = plan.monthly_post_minutes

    # ── 3. Public pool count ──────────────────────────────────────────────────

    public_pool_count: int = db.execute(
        select(func.count(CollectionCase.id)).where(
            CollectionCase.tenant_id == tenant_id,
            CollectionCase.pool_type == "public",
        )
    ).scalar() or 0

    # ── 4. Risk alert count (last 7 days) ─────────────────────────────────────
    # RiskEvent has no tenant_id — join via CallRecord
    risk_alert_count_7d: int = db.execute(
        select(func.count(RiskEvent.id))
        .join(CallRecord, RiskEvent.call_id == CallRecord.id)
        .where(
            CallRecord.tenant_id == tenant_id,
            RiskEvent.created_at >= seven_days_ago,
        )
    ).scalar() or 0

    # ── 5. Top agents (by today's call count) ────────────────────────────────

    today_calls_by_user: dict[int, int] = dict(
        db.execute(
            select(CallRecord.caller_user_id, func.count(CallRecord.id))
            .where(
                CallRecord.tenant_id == tenant_id,
                CallRecord.started_at >= today_start,
                CallRecord.started_at < today_end,
            )
            .group_by(CallRecord.caller_user_id)
        ).all()
    )

    agent_users = db.execute(
        select(UserAccount.id, UserAccount.name)
        .join(UserTenantMembership, UserAccount.id == UserTenantMembership.user_id)
        .where(
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.role.in_(["agent_internal", "agent_external"]),
            UserTenantMembership.is_active.is_(True),
        )
    ).all()

    # 当月每位坐席的 promise 通话数：按 caller_user_id 聚合 AnalysisResult.key_segments['intent']
    month_promised_by_user = _count_month_promised_by_user(db, tenant_id, month_start, today_end)

    rankings = [
        AgentRanking(
            user_id=u.id,
            name=u.name,
            today_calls=today_calls_by_user.get(u.id, 0),
            month_promised=month_promised_by_user.get(u.id, 0),
        )
        for u in agent_users
    ]
    rankings.sort(key=lambda r: r.today_calls, reverse=True)
    top_agents = rankings[:10]

    # ── 6. Script adoption trend (last 7 days) ────────────────────────────────
    # SuggestionFeedback has no tenant_id — join via CallRecord
    trend: list[float] = []
    for i in range(7):
        day_start = today_start - timedelta(days=6 - i)
        day_end = day_start + timedelta(days=1)

        row = db.execute(
            select(
                func.count(SuggestionFeedback.id),
                func.sum(
                    sa.case(
                        (SuggestionFeedback.action == "adopt", 1),
                        else_=0,
                    )
                ),
            )
            .join(CallRecord, SuggestionFeedback.call_id == CallRecord.id)
            .where(
                CallRecord.tenant_id == tenant_id,
                SuggestionFeedback.created_at >= day_start,
                SuggestionFeedback.created_at < day_end,
            )
        ).one()
        total_fb, adopted_fb = row[0] or 0, row[1] or 0
        trend.append(round(adopted_fb / total_fb, 3) if total_fb > 0 else 0.0)

    return AdminDashboardStats(
        today=TodayStats(
            outbound_count=outbound_count,
            connected_count=connected_count,
            promised_count=promised_count,
            recovered_amount=recovered_amount,
        ),
        minute_quota=QuotaStats(
            used_min=used_min,
            total_min=total_min,
            remaining_min=remaining_min,
            warning=warning,
            realtime_min=realtime_min,
            post_min=post_min,
            realtime_quota=realtime_quota,
            post_quota=post_quota,
        ),
        public_pool_count=public_pool_count,
        risk_alert_count_7d=risk_alert_count_7d,
        top_agents=top_agents,
        script_adoption_trend=trend,
    )


def _count_promised(
    db: Session,
    tenant_id: int,
    start: datetime,
    end: datetime,
) -> int:
    """Count AnalysisResult rows where key_segments['intent'] is a promise intent.

    key_segments is stored as JSON. We fetch all analysis results for today's
    calls and filter in Python — avoids relying on DB-specific JSON operators
    and works for both PostgreSQL and SQLite (used in some edge cases).
    """
    rows = db.execute(
        select(AnalysisResult.key_segments)
        .join(CallRecord, AnalysisResult.call_id == CallRecord.id)
        .where(
            CallRecord.tenant_id == tenant_id,
            CallRecord.started_at >= start,
            CallRecord.started_at < end,
        )
    ).scalars().all()

    count = 0
    for segments in rows:
        if segments and isinstance(segments, dict):
            if segments.get("intent") in _PROMISE_INTENTS:
                count += 1
    return count


def _sum_promised_amount(
    db: Session,
    tenant_id: int,
    start: datetime,
    end: datetime,
) -> float:
    """Sum CollectionCase.amount_owed for calls in [start,end) whose intent is promise."""
    rows = db.execute(
        select(AnalysisResult.key_segments, CollectionCase.amount_owed)
        .join(CallRecord, AnalysisResult.call_id == CallRecord.id)
        .join(CollectionCase, CallRecord.case_id == CollectionCase.id)
        .where(
            CallRecord.tenant_id == tenant_id,
            CallRecord.started_at >= start,
            CallRecord.started_at < end,
        )
    ).all()

    total = 0.0
    for segments, amount in rows:
        if not (segments and isinstance(segments, dict)):
            continue
        if segments.get("intent") not in _PROMISE_INTENTS:
            continue
        if amount is None:
            continue
        total += float(amount)
    return round(total, 2)


def _count_month_promised_by_user(
    db: Session,
    tenant_id: int,
    start: datetime,
    end: datetime,
) -> dict[int, int]:
    """Per-caller count of promise calls in [start,end)."""
    rows = db.execute(
        select(CallRecord.caller_user_id, AnalysisResult.key_segments)
        .join(AnalysisResult, AnalysisResult.call_id == CallRecord.id)
        .where(
            CallRecord.tenant_id == tenant_id,
            CallRecord.started_at >= start,
            CallRecord.started_at < end,
        )
    ).all()

    counts: dict[int, int] = {}
    for caller_user_id, segments in rows:
        if caller_user_id is None:
            continue
        if not (segments and isinstance(segments, dict)):
            continue
        if segments.get("intent") not in _PROMISE_INTENTS:
            continue
        counts[caller_user_id] = counts.get(caller_user_id, 0) + 1
    return counts


@router.get("/dashboard/by-project", response_model=list[ProjectKpi])
def get_dashboard_by_project(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[ProjectKpi]:
    """v1.4 — 按项目分维度看 KPI（admin/物业管理员/督导都能看）"""
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        return []
    tenant_id = int(tenant_id)

    projects = db.execute(
        select(Project).where(Project.tenant_id == tenant_id).order_by(Project.id)
    ).scalars().all()

    now = datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)
    items: list[ProjectKpi] = []

    for p in projects:
        case_rows = db.execute(
            select(CollectionCase.stage, CollectionCase.amount_owed).where(
                CollectionCase.tenant_id == tenant_id,
                CollectionCase.project_id == p.id,
            )
        ).all()
        case_count = len(case_rows)
        receivable = 0.0
        received = 0.0
        promised = in_progress = new_c = escalated = closed = 0
        for stage, amt in case_rows:
            amt_f = float(amt or 0)
            receivable += amt_f
            if stage == "paid":
                received += amt_f
                closed += 1
            elif stage == "closed":
                closed += 1
            elif stage == "promised":
                promised += 1
            elif stage == "in_progress":
                in_progress += 1
            elif stage == "new":
                new_c += 1
            elif stage == "escalated":
                escalated += 1

        # 通话数 30 天
        total_calls = db.execute(
            select(func.count(CallRecord.id))
            .join(CollectionCase, CollectionCase.id == CallRecord.case_id)
            .where(
                CallRecord.tenant_id == tenant_id,
                CollectionCase.project_id == p.id,
                CallRecord.started_at >= cutoff_30d,
            )
        ).scalar_one() or 0
        connected = db.execute(
            select(func.count(CallRecord.id))
            .join(CollectionCase, CollectionCase.id == CallRecord.case_id)
            .where(
                CallRecord.tenant_id == tenant_id,
                CollectionCase.project_id == p.id,
                CallRecord.started_at >= cutoff_30d,
                CallRecord.duration_sec > 10,
            )
        ).scalar_one() or 0

        provider_name = None
        if p.provider_id:
            provider_name = db.execute(
                select(ServiceProvider.name).where(ServiceProvider.id == p.provider_id)
            ).scalar_one_or_none()

        items.append(ProjectKpi(
            project_id=p.id,
            project_name=p.name,
            provider_id=p.provider_id,
            provider_name=provider_name,
            case_count=case_count,
            receivable=round(receivable, 2),
            received=round(received, 2),
            recovery_rate=round(received / receivable, 4) if receivable > 0 else 0.0,
            promised_count=promised,
            in_progress_count=in_progress,
            new_count=new_c,
            escalated_count=escalated,
            closed_count=closed,
            connected_30d=int(connected),
            total_calls_30d=int(total_calls),
        ))

    return items


@router.get("/dashboard/by-provider", response_model=list[ProviderKpi])
def get_dashboard_by_provider(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[ProviderKpi]:
    """v1.5 — 按服务商分维度看 KPI（多服务商相对表现排名）。

    数据源：本租户活跃项目（status='active'）的 provider_id 聚合。
    """
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        return []
    tenant_id = int(tenant_id)

    # 找本租户所有有 provider 的活跃项目
    project_rows = db.execute(
        select(Project.id, Project.provider_id).where(
            Project.tenant_id == tenant_id,
            Project.provider_id.is_not(None),
            Project.status == "active",
        )
    ).all()
    if not project_rows:
        return []

    # group projects by provider
    by_provider: dict[int, list[int]] = {}
    for pid, provider_id in project_rows:
        by_provider.setdefault(int(provider_id), []).append(int(pid))

    now = datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)
    items: list[ProviderKpi] = []

    for provider_id, project_ids in by_provider.items():
        provider_name = db.execute(
            select(ServiceProvider.name).where(ServiceProvider.id == provider_id)
        ).scalar_one_or_none() or f"#{provider_id}"

        case_rows = db.execute(
            select(CollectionCase.stage, CollectionCase.amount_owed).where(
                CollectionCase.tenant_id == tenant_id,
                CollectionCase.project_id.in_(project_ids),
            )
        ).all()
        case_count = len(case_rows)
        paid_count = 0
        receivable = 0.0
        recovered = 0.0
        for stage, amt in case_rows:
            amt_f = float(amt or 0)
            receivable += amt_f
            if stage == "paid":
                paid_count += 1
                recovered += amt_f

        total_calls = db.execute(
            select(func.count(CallRecord.id))
            .join(CollectionCase, CollectionCase.id == CallRecord.case_id)
            .where(
                CallRecord.tenant_id == tenant_id,
                CollectionCase.project_id.in_(project_ids),
                CallRecord.started_at >= cutoff_30d,
            )
        ).scalar_one() or 0
        connected = db.execute(
            select(func.count(CallRecord.id))
            .join(CollectionCase, CollectionCase.id == CallRecord.case_id)
            .where(
                CallRecord.tenant_id == tenant_id,
                CollectionCase.project_id.in_(project_ids),
                CallRecord.started_at >= cutoff_30d,
                CallRecord.duration_sec > 10,
            )
        ).scalar_one() or 0

        items.append(ProviderKpi(
            provider_id=provider_id,
            provider_name=provider_name,
            active_project_count=len(project_ids),
            case_count=case_count,
            paid_count=paid_count,
            paid_rate=round(paid_count / case_count, 4) if case_count else 0.0,
            receivable=round(receivable, 2),
            recovered_30d=round(recovered, 2),
            call_count_30d=int(total_calls),
            connected_rate_30d=round(
                connected / total_calls, 4
            ) if total_calls else 0.0,
        ))

    items.sort(key=lambda x: x.recovered_30d, reverse=True)
    return items[:10]
