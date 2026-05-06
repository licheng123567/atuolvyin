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
from app.models.case import CollectionCase
from app.models.audit import PlanConfig
from app.models.tenant import Tenant, TenantMinuteUsage, UserTenantMembership
from app.models.user import UserAccount
from app.schemas.dashboard import (
    AdminDashboardStats,
    AgentRanking,
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

    rankings = [
        AgentRanking(
            user_id=u.id,
            name=u.name,
            today_calls=today_calls_by_user.get(u.id, 0),
            month_promised=0,  # TODO(sprint-settlement): query AnalysisResult for full month
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
            recovered_amount=0.0,
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
