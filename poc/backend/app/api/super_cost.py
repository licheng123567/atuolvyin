"""Sprint 15 — Cost dashboard aggregating tenant minute usage platform-wide.

GET /api/v1/super/cost/dashboard
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_roles
from app.models.tenant import Tenant, TenantMinuteUsage
from app.models.user import UserAccount

router = APIRouter()

SUPER_ROLES = ("platform_super", "platform_superadmin")


class TenantUsageItem(BaseModel):
    tenant_id: int
    name: str
    used_minutes: int  # 总分钟（兼容字段）
    realtime_minutes: int = 0  # Sprint 14.1
    post_minutes: int = 0  # Sprint 14.1
    quota: int | None
    utilization_pct: float


class MonthlyTrendPoint(BaseModel):
    year_month: str
    total_used: int


class CostDashboardOut(BaseModel):
    total_quota_pool: int
    total_used_this_month: int
    total_realtime_this_month: int = 0  # Sprint 14.1
    total_post_this_month: int = 0  # Sprint 14.1
    tenant_ranking: list[TenantUsageItem]
    monthly_trend: list[MonthlyTrendPoint]


def _shift_year_month(year: int, month: int, delta: int) -> str:
    idx = year * 12 + (month - 1) + delta
    y = idx // 12
    m = idx % 12 + 1
    return f"{y:04d}-{m:02d}"


@router.get("/cost/dashboard", response_model=CostDashboardOut)
async def get_cost_dashboard(
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CostDashboardOut:
    now = datetime.now(UTC)
    current_ym = now.strftime("%Y-%m")

    # ── Total quota pool (sum of all tenant.monthly_minute_quota) ──
    total_quota_pool: int = (
        db.execute(select(func.coalesce(func.sum(Tenant.monthly_minute_quota), 0))).scalar() or 0
    )

    # ── Total used this month ─────────────────────────────────
    totals = db.execute(
        select(
            func.coalesce(func.sum(TenantMinuteUsage.used_minutes), 0),
            func.coalesce(func.sum(TenantMinuteUsage.realtime_minutes), 0),
            func.coalesce(func.sum(TenantMinuteUsage.post_minutes), 0),
        ).where(TenantMinuteUsage.year_month == current_ym)
    ).first()
    total_used_this_month = int(totals[0]) if totals else 0
    total_realtime_this_month = int(totals[1]) if totals else 0
    total_post_this_month = int(totals[2]) if totals else 0

    # ── Top-10 tenants by used minutes (current month) ────────
    rows = db.execute(
        select(
            Tenant.id,
            Tenant.name,
            Tenant.monthly_minute_quota,
            func.coalesce(TenantMinuteUsage.used_minutes, 0).label("used"),
            func.coalesce(TenantMinuteUsage.realtime_minutes, 0).label("rt"),
            func.coalesce(TenantMinuteUsage.post_minutes, 0).label("po"),
        )
        .outerjoin(
            TenantMinuteUsage,
            (TenantMinuteUsage.tenant_id == Tenant.id)
            & (TenantMinuteUsage.year_month == current_ym),
        )
        .order_by(func.coalesce(TenantMinuteUsage.used_minutes, 0).desc())
        .limit(10)
    ).all()

    ranking: list[TenantUsageItem] = []
    for tid, tname, quota, used, rt, po in rows:
        used_int = int(used or 0)
        utilization_pct = round(used_int / quota * 100, 2) if quota and quota > 0 else 0.0
        ranking.append(
            TenantUsageItem(
                tenant_id=tid,
                name=tname,
                used_minutes=used_int,
                realtime_minutes=int(rt or 0),
                post_minutes=int(po or 0),
                quota=quota,
                utilization_pct=utilization_pct,
            )
        )

    # ── Monthly trend (last 6 months including current) ───────
    months: list[str] = [_shift_year_month(now.year, now.month, -i) for i in range(5, -1, -1)]
    trend_rows = dict(
        db.execute(
            select(
                TenantMinuteUsage.year_month,
                func.coalesce(func.sum(TenantMinuteUsage.used_minutes), 0),
            )
            .where(TenantMinuteUsage.year_month.in_(months))
            .group_by(TenantMinuteUsage.year_month)
        ).all()
    )
    monthly_trend = [
        MonthlyTrendPoint(year_month=ym, total_used=int(trend_rows.get(ym, 0))) for ym in months
    ]

    return CostDashboardOut(
        total_quota_pool=int(total_quota_pool),
        total_used_this_month=int(total_used_this_month),
        total_realtime_this_month=total_realtime_this_month,
        total_post_this_month=total_post_this_month,
        tenant_ranking=ranking,
        monthly_trend=monthly_trend,
    )
