"""v1.0.0 — 服务商合规月报(对齐物业 admin/compliance)。

诱因:用户反馈服务商应该也有合规月报。

scope:
  - 本服务商接的所有案件(Project.provider_id == self_provider)的通话 / 风险事件
  - 跨多物业聚合(服务商可能服务多个物业,这里数据是服务商角度)

数据源同 admin_compliance,只是 WHERE 条件改成 Project.provider_id == self。
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
from app.core.security import get_token_payload, require_provider_roles
from app.models.call import CallRecord, RiskEvent
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.tenant import ServiceProvider, UserTenantMembership
from app.schemas.compliance import (
    ComplianceMonthlyReport,
    ComplianceReportListItem,
    RiskEventBucket,
)

router = APIRouter()

PROVIDER_ADMIN_ROLES = ("admin",)

AFTER_HOURS_START_UTC_HOUR = 13  # 21:00 +08
AFTER_HOURS_END_UTC_HOUR = 1  # 09:00 +08


def _resolve_provider_id(payload: dict, db: Session) -> int:
    user_id = int(payload.get("user_id") or 0)
    if not user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Invalid token"},
        )
    membership = (
        db.execute(
            select(UserTenantMembership)
            .where(UserTenantMembership.user_id == user_id)
            .where(UserTenantMembership.provider_id.isnot(None))
        )
        .scalars()
        .first()
    )
    if membership is None or membership.provider_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NO_PROVIDER", "message": "当前账号未绑定任何服务商"},
        )
    return int(membership.provider_id)


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


def _provider_call_filter(stmt, provider_id: int, start: datetime, end: datetime):
    """构造 scope 通用 WHERE:本服务商接的案件 + 月份。

    CallRecord JOIN CollectionCase JOIN Project,Project.provider_id == self.
    """
    return (
        stmt.join(CollectionCase, CollectionCase.id == CallRecord.case_id)
        .join(Project, Project.id == CollectionCase.project_id)
        .where(Project.provider_id == provider_id)
        .where(CallRecord.created_at >= start)
        .where(CallRecord.created_at < end)
    )


def _compute_month_summary(
    db: Session, provider_id: int, year: int, month: int
) -> tuple[int, int, int, int]:
    start, end = _month_bounds(year, month)

    total_calls = (
        db.execute(
            _provider_call_filter(
                select(func.count()).select_from(CallRecord),
                provider_id,
                start,
                end,
            )
        ).scalar_one()
        or 0
    )

    total_risk = (
        db.execute(
            select(func.count(RiskEvent.id))
            .join(CallRecord, CallRecord.id == RiskEvent.call_id)
            .join(CollectionCase, CollectionCase.id == CallRecord.case_id)
            .join(Project, Project.id == CollectionCase.project_id)
            .where(Project.provider_id == provider_id)
            .where(CallRecord.created_at >= start)
            .where(CallRecord.created_at < end)
        ).scalar_one()
        or 0
    )

    dnc = (
        db.execute(
            select(func.count(CallRecord.id))
            .join(CollectionCase, CollectionCase.id == CallRecord.case_id)
            .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
            .join(Project, Project.id == CollectionCase.project_id)
            .where(Project.provider_id == provider_id)
            .where(CallRecord.created_at >= start)
            .where(CallRecord.created_at < end)
            .where(OwnerProfile.do_not_call.is_(True))
        ).scalar_one()
        or 0
    )

    # 超频:本服务商接的案件月内联系超 3 次(月份不依赖,monthly_contact_count 是当月计数)
    overfreq = (
        db.execute(
            select(func.count(CollectionCase.id))
            .join(Project, Project.id == CollectionCase.project_id)
            .where(Project.provider_id == provider_id)
            .where(CollectionCase.monthly_contact_count > 3)
        ).scalar_one()
        or 0
    )

    return int(total_calls), int(total_risk), int(dnc), int(overfreq)


@router.get("/compliance/monthly", response_model=list[ComplianceReportListItem])
def list_provider_monthly_reports(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    months: int = Query(6, ge=1, le=24),
) -> list[ComplianceReportListItem]:
    provider_id = _resolve_provider_id(payload, db)
    now = datetime.now(UTC)

    items: list[ComplianceReportListItem] = []
    year, month = now.year, now.month
    for _ in range(months):
        ym = f"{year:04d}-{month:02d}"
        total_calls, total_risk, dnc, _of = _compute_month_summary(db, provider_id, year, month)
        items.append(
            ComplianceReportListItem(
                year_month=ym,
                total_calls=total_calls,
                total_risk_events=total_risk,
                do_not_call_violations=dnc,
            )
        )
        if month == 1:
            year -= 1
            month = 12
        else:
            month -= 1
    return items


@router.get("/compliance/monthly/{year_month}", response_model=ComplianceMonthlyReport)
def get_provider_monthly_report(
    year_month: Annotated[str, Path(pattern=r"^\d{4}-\d{2}$")],
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ComplianceMonthlyReport:
    provider_id = _resolve_provider_id(payload, db)
    year, month = _parse_year_month(year_month)
    start, end = _month_bounds(year, month)

    provider = db.get(ServiceProvider, provider_id)
    if provider is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "服务商不存在"},
        )

    # 拉本服务商接的案件下的所有通话
    calls = (
        db.execute(
            select(CallRecord)
            .join(CollectionCase, CollectionCase.id == CallRecord.case_id)
            .join(Project, Project.id == CollectionCase.project_id)
            .where(Project.provider_id == provider_id)
            .where(CallRecord.created_at >= start)
            .where(CallRecord.created_at < end)
        )
        .scalars()
        .all()
    )

    total_calls = len(calls)
    total_minutes = sum((c.billable_duration or 0) for c in calls) // 60

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
        .join(CollectionCase, CollectionCase.id == CallRecord.case_id)
        .join(Project, Project.id == CollectionCase.project_id)
        .where(Project.provider_id == provider_id)
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

    _, _, dnc, overfreq = _compute_month_summary(db, provider_id, year, month)

    return ComplianceMonthlyReport(
        year_month=year_month,
        tenant_name=provider.name,  # 复用 schema 字段,放服务商名称
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
