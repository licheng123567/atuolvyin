"""Sprint 8.4 — Compliance Monthly Report (PRD §3.13 / L2048).

物业管理员的合规月报：
  - 列出最近 N 个月的概览（每月一行）
  - 按 YYYY-MM 拉单月详细报告（计算 on-the-fly，无落库）

PDF 导出策略：服务端只输出结构化数据，前端用 print-friendly CSS 渲染 +
浏览器「打印为 PDF」即可。等真实需求出现再引入 reportlab/weasyprint。
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.call import CallRecord, RiskEvent
from app.models.case import CollectionCase, OwnerProfile
from app.models.tenant import Tenant
from app.schemas.compliance import (
    ComplianceMonthlyReport,
    ComplianceReportListItem,
    RiskEventBucket,
)

router = APIRouter()

ADMIN_ROLES = ("admin", "platform_superadmin")

# Allowed daytime window for outbound calls (Beijing local, but stored UTC).
# Calls happening outside [09:00, 21:00] UTC+8 == [01:00, 13:00] UTC are flagged.
AFTER_HOURS_START_UTC_HOUR = 13  # 21:00 +08
AFTER_HOURS_END_UTC_HOUR = 1  # 09:00 +08


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=UTC)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(year, month + 1, 1, tzinfo=UTC)
    return start, end


def _parse_year_month(year_month: str) -> tuple[int, int]:
    try:
        y, m = year_month.split("-")
        year, month = int(y), int(m)
        if not 1 <= month <= 12:
            raise ValueError("month out of range")
        return year, month
    except (ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "ERR_VALIDATION",
                "message": "year_month 格式应为 YYYY-MM",
            },
        ) from exc


def _compute_month_summary(
    db: Session, tenant_id: int, year: int, month: int
) -> tuple[int, int, int, int]:
    """Cheap per-month tuple: (total_calls, total_risk_events, dnc_violations,
    overfreq_violations). Used for the list view to avoid heavy detail compute."""
    start, end = _month_bounds(year, month)

    total_calls = (
        db.execute(
            select(func.count())
            .select_from(CallRecord)
            .where(CallRecord.tenant_id == tenant_id)
            .where(CallRecord.created_at >= start)
            .where(CallRecord.created_at < end)
        ).scalar_one()
        or 0
    )

    total_risk = (
        db.execute(
            select(func.count())
            .select_from(RiskEvent)
            .join(CallRecord, CallRecord.id == RiskEvent.call_id)
            .where(CallRecord.tenant_id == tenant_id)
            .where(CallRecord.created_at >= start)
            .where(CallRecord.created_at < end)
        ).scalar_one()
        or 0
    )

    # 对 do_not_call=true 的业主仍发起的通话
    dnc = (
        db.execute(
            select(func.count())
            .select_from(CallRecord)
            .join(CollectionCase, CollectionCase.id == CallRecord.case_id)
            .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
            .where(CallRecord.tenant_id == tenant_id)
            .where(CallRecord.created_at >= start)
            .where(CallRecord.created_at < end)
            .where(OwnerProfile.do_not_call.is_(True))
        ).scalar_one()
        or 0
    )

    # 月内联系超过 3 次的案件数
    overfreq = (
        db.execute(
            select(func.count())
            .select_from(CollectionCase)
            .where(CollectionCase.tenant_id == tenant_id)
            .where(CollectionCase.monthly_contact_count > 3)
        ).scalar_one()
        or 0
    )

    return int(total_calls), int(total_risk), int(dnc), int(overfreq)


@router.get("/compliance/monthly", response_model=list[ComplianceReportListItem])
def list_monthly_reports(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    months: int = Query(6, ge=1, le=24),
) -> list[ComplianceReportListItem]:
    tenant_id = int(payload.get("tenant_id") or 0)
    now = datetime.now(UTC)

    items: list[ComplianceReportListItem] = []
    year, month = now.year, now.month
    for _ in range(months):
        ym = f"{year:04d}-{month:02d}"
        total_calls, total_risk, dnc, _of = _compute_month_summary(db, tenant_id, year, month)
        items.append(
            ComplianceReportListItem(
                year_month=ym,
                total_calls=total_calls,
                total_risk_events=total_risk,
                do_not_call_violations=dnc,
            )
        )
        # 上一个月
        if month == 1:
            year -= 1
            month = 12
        else:
            month -= 1
    return items


@router.get("/compliance/monthly/{year_month}", response_model=ComplianceMonthlyReport)
def get_monthly_report(
    year_month: Annotated[str, Path(pattern=r"^\d{4}-\d{2}$")],
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ComplianceMonthlyReport:
    tenant_id = int(payload.get("tenant_id") or 0)
    year, month = _parse_year_month(year_month)
    start, end = _month_bounds(year, month)

    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "租户不存在"},
        )

    calls = (
        db.execute(
            select(CallRecord)
            .where(CallRecord.tenant_id == tenant_id)
            .where(CallRecord.created_at >= start)
            .where(CallRecord.created_at < end)
        )
        .scalars()
        .all()
    )

    total_calls = len(calls)
    total_minutes = sum((c.billable_duration or 0) for c in calls) // 60

    # 时段外（北京 09-21 之外）— 用 created_at UTC 推断
    after_hours = sum(
        1
        for c in calls
        if c.created_at
        and (
            c.created_at.hour >= AFTER_HOURS_START_UTC_HOUR
            or c.created_at.hour < AFTER_HOURS_END_UTC_HOUR
        )
    )

    risk_rows = db.execute(
        select(RiskEvent.level, RiskEvent.category, RiskEvent.intervention)
        .join(CallRecord, CallRecord.id == RiskEvent.call_id)
        .where(CallRecord.tenant_id == tenant_id)
        .where(CallRecord.created_at >= start)
        .where(CallRecord.created_at < end)
    ).all()
    by_level: Counter[str] = Counter()
    by_cat: dict[tuple[str, str], int] = defaultdict(int)
    interrupted = 0
    for level, category, intervention in risk_rows:
        by_level[level] += 1
        by_cat[(level, category)] += 1
        if intervention in ("interrupt", "terminate"):
            interrupted += 1

    _, _, dnc, overfreq = _compute_month_summary(db, tenant_id, year, month)

    return ComplianceMonthlyReport(
        year_month=year_month,
        tenant_name=tenant.name,
        period_start=start.date().isoformat(),
        period_end=end.date().isoformat(),
        total_calls=total_calls,
        total_minutes=total_minutes,
        total_risk_events=sum(by_level.values()),
        risk_events_by_level={k: int(v) for k, v in by_level.items()},
        risk_events_by_category=[
            RiskEventBucket(level=lvl, category=cat, count=cnt)
            for (lvl, cat), cnt in sorted(by_cat.items(), key=lambda kv: -kv[1])
        ],
        do_not_call_violations=dnc,
        after_hours_calls=after_hours,
        overfreq_violations=overfreq,
        interrupted_calls=interrupted,
        generated_at=datetime.now(UTC).isoformat(),
    )
