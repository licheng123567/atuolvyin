"""Sprint 11.4 — Agent personal performance dashboard (PRD §5B / L2099).

PC view (App side handled in Android Sprint 11.5/.7/.9). Returns the current
month's calls / connected / promised / paid + minute quota usage + tenant rank.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.call import CallRecord
from app.models.case import CollectionCase
from app.models.tenant import Tenant, TenantMinuteUsage
from app.models.user import UserAccount
from pydantic import BaseModel

router = APIRouter()

AGENT_ROLES = ("agent_internal", "agent_external")


class AgentPerformanceOut(BaseModel):
    user_id: int
    name: str
    year_month: str
    month_calls: int
    month_connected: int
    month_promised_cases: int
    month_paid_cases: int
    month_paid_amount: Decimal
    conversion_rate: float | None
    minutes_used: int
    minutes_quota: int | None
    rank_in_tenant: int  # 1-based; 0 if no peers


@router.get("/me/performance", response_model=AgentPerformanceOut)
def get_my_performance(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> AgentPerformanceOut:
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )

    me = db.get(UserAccount, user_id)
    if me is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "用户不存在"},
        )

    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (
        month_start.replace(year=month_start.year + 1, month=1)
        if month_start.month == 12
        else month_start.replace(month=month_start.month + 1)
    )
    year_month = month_start.strftime("%Y-%m")

    # Calls in this month for me
    call_row = db.execute(
        select(
            func.count().label("total"),
            func.sum(case((CallRecord.billable_duration > 0, 1), else_=0)).label("connected"),
            func.coalesce(func.sum(CallRecord.billable_duration), 0).label("billable"),
        )
        .where(CallRecord.tenant_id == tenant_id)
        .where(CallRecord.caller_user_id == user_id)
        .where(CallRecord.created_at >= month_start)
        .where(CallRecord.created_at < next_month)
    ).first()
    month_calls = int(call_row.total or 0)
    month_connected = int(call_row.connected or 0)

    # Promised + paid cases (snapshot — not strictly limited to month)
    promised = (
        db.execute(
            select(func.count())
            .select_from(CollectionCase)
            .where(CollectionCase.tenant_id == tenant_id)
            .where(CollectionCase.assigned_to == user_id)
            .where(CollectionCase.stage == "promised")
        ).scalar_one()
        or 0
    )
    paid_row = db.execute(
        select(
            func.count().label("count"),
            func.coalesce(func.sum(CollectionCase.amount_owed), 0).label("amount"),
        )
        .where(CollectionCase.tenant_id == tenant_id)
        .where(CollectionCase.assigned_to == user_id)
        .where(CollectionCase.stage == "paid")
    ).first()

    # Minute usage
    usage = db.execute(
        select(TenantMinuteUsage).where(
            TenantMinuteUsage.tenant_id == tenant_id,
            TenantMinuteUsage.year_month == year_month,
        )
    ).scalar_one_or_none()
    minutes_used = int(usage.used_minutes) if usage else 0
    tenant = db.get(Tenant, tenant_id)
    minutes_quota = tenant.monthly_minute_quota if tenant else None

    # Rank by month_calls within same tenant
    peer_rows = db.execute(
        select(CallRecord.caller_user_id, func.count())
        .where(CallRecord.tenant_id == tenant_id)
        .where(CallRecord.created_at >= month_start)
        .where(CallRecord.created_at < next_month)
        .group_by(CallRecord.caller_user_id)
    ).all()
    peer_calls = sorted([int(c) for _, c in peer_rows], reverse=True)
    rank = 0
    for i, c in enumerate(peer_calls, start=1):
        if c == month_calls:
            rank = i
            break

    return AgentPerformanceOut(
        user_id=me.id,
        name=me.name,
        year_month=year_month,
        month_calls=month_calls,
        month_connected=month_connected,
        month_promised_cases=int(promised),
        month_paid_cases=int(paid_row.count or 0),
        month_paid_amount=Decimal(str(paid_row.amount or 0)),
        conversion_rate=(promised / month_calls) if month_calls else None,
        minutes_used=minutes_used,
        minutes_quota=minutes_quota,
        rank_in_tenant=rank,
    )
