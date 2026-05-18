"""Sprint 9.4 + 9.5 — Supervisor extras (PRD §4.6, §4.7).

Endpoints:
  - GET  /supervisor/risk-events       — 按督导 scope（物业 / 本服务商）过滤的 RiskEvent 时间线
  - PATCH /supervisor/risk-events/{id} — 添加 / 更新 disposition_note
  - GET  /supervisor/team-performance  — 团队成员排名 + 与上一周期对比
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.call import CallRecord, RiskEvent
from app.models.case import CollectionCase
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.schemas.supervisor import (
    RiskEventNoteIn,
    RiskEventTimelineItem,
    TeamPerformanceItem,
    TeamPerformanceOut,
)

from ._supervisor_scope import (
    SupervisorScope,
    supervisor_agent_filter,
    supervisor_call_filter,
    supervisor_case_filter,
    supervisor_scope,
)

router = APIRouter()

SUPERVISOR_ROLES = ("supervisor", "admin")


# ── Sprint 9.4: risk events timeline ────────────────────────────────


@router.get("/risk-events", response_model=list[RiskEventTimelineItem])
def list_risk_events(
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
    level: str | None = Query(None, pattern=r"^L[1-3]$"),
    period_days: int = Query(7, ge=1, le=90),
    limit: int = Query(200, ge=1, le=500),
) -> list[RiskEventTimelineItem]:
    cutoff = datetime.now(UTC) - timedelta(days=period_days)

    stmt = (
        select(RiskEvent, CallRecord, UserAccount)
        .join(CallRecord, CallRecord.id == RiskEvent.call_id)
        .outerjoin(UserAccount, UserAccount.id == CallRecord.caller_user_id)
        .where(supervisor_call_filter(scope))
        .where(RiskEvent.created_at >= cutoff)
    )
    if level:
        stmt = stmt.where(RiskEvent.level == level)
    rows = db.execute(stmt.order_by(RiskEvent.created_at.desc()).limit(limit)).all()

    return [
        RiskEventTimelineItem(
            id=r.id,
            call_id=r.call_id,
            case_id=c.case_id,
            level=r.level,
            category=r.category,
            intervention=r.intervention,
            trigger_text=r.trigger_text,
            audio_offset_ms=r.audio_offset_ms,
            occurred_at=r.created_at,
            disposition_note=r.disposition_note,
            disposition_at=r.disposition_at,
            agent_user_id=u.id if u else None,
            agent_name=u.name if u else None,
        )
        for r, c, u in rows
    ]


@router.patch("/risk-events/{event_id}", response_model=RiskEventTimelineItem)
def annotate_risk_event(
    event_id: int,
    body: RiskEventNoteIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> RiskEventTimelineItem:
    user_id = int(payload.get("user_id") or 0)

    row = db.execute(
        select(RiskEvent, CallRecord)
        .join(CallRecord, CallRecord.id == RiskEvent.call_id)
        .where(RiskEvent.id == event_id)
        .where(supervisor_call_filter(scope))
    ).first()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "风控事件不存在"},
        )
    event, call = row

    event.disposition_note = body.note
    event.disposition_by = user_id
    event.disposition_at = datetime.now(UTC)
    db.commit()
    db.refresh(event)

    agent = db.get(UserAccount, call.caller_user_id) if call.caller_user_id else None

    return RiskEventTimelineItem(
        id=event.id,
        call_id=event.call_id,
        case_id=call.case_id,
        level=event.level,
        category=event.category,
        intervention=event.intervention,
        trigger_text=event.trigger_text,
        audio_offset_ms=event.audio_offset_ms,
        occurred_at=event.created_at,
        disposition_note=event.disposition_note,
        disposition_at=event.disposition_at,
        agent_user_id=agent.id if agent else None,
        agent_name=agent.name if agent else None,
    )


# ── Sprint 9.5: team performance with period-over-period delta ──────


@router.get("/team-performance", response_model=TeamPerformanceOut)
def team_performance(
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
    period_days: int = Query(7, ge=1, le=90),
) -> TeamPerformanceOut:
    now = datetime.now(UTC)
    cur_start = now - timedelta(days=period_days)
    prev_start = now - timedelta(days=period_days * 2)
    prev_end = cur_start

    # All agents visible in this supervisor's scope
    agent_rows = db.execute(
        select(UserAccount.id, UserAccount.name)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(supervisor_agent_filter(scope))
        .where(UserTenantMembership.is_active.is_(True))
    ).all()
    agent_ids = [r.id for r in agent_rows]
    if not agent_ids:
        return TeamPerformanceOut(period_days=period_days, items=[])

    def _calls_window(start: datetime, end: datetime) -> dict[int, tuple[int, int]]:
        rows = db.execute(
            select(
                CallRecord.caller_user_id,
                func.count().label("total"),
                func.sum(case((CallRecord.billable_duration > 0, 1), else_=0)).label("connected"),
            )
            .where(supervisor_call_filter(scope))
            .where(CallRecord.caller_user_id.in_(agent_ids))
            .where(CallRecord.created_at >= start)
            .where(CallRecord.created_at < end)
            .group_by(CallRecord.caller_user_id)
        ).all()
        return {r.caller_user_id: (int(r.total or 0), int(r.connected or 0)) for r in rows}

    cur_calls = _calls_window(cur_start, now)
    prev_calls = _calls_window(prev_start, prev_end)

    promised_rows = db.execute(
        select(CollectionCase.assigned_to, func.count())
        .where(supervisor_case_filter(scope))
        .where(CollectionCase.assigned_to.in_(agent_ids))
        .where(CollectionCase.stage == "promised")
        .group_by(CollectionCase.assigned_to)
    ).all()
    promised_by_user = {r[0]: int(r[1]) for r in promised_rows}

    paid_rows = db.execute(
        select(CollectionCase.assigned_to, func.count())
        .where(supervisor_case_filter(scope))
        .where(CollectionCase.assigned_to.in_(agent_ids))
        .where(CollectionCase.stage == "paid")
        .group_by(CollectionCase.assigned_to)
    ).all()
    paid_by_user = {r[0]: int(r[1]) for r in paid_rows}

    items: list[TeamPerformanceItem] = []
    for r in agent_rows:
        cur_total, cur_conn = cur_calls.get(r.id, (0, 0))
        prev_total, _ = prev_calls.get(r.id, (0, 0))
        delta: float | None
        if prev_total > 0:
            delta = (cur_total - prev_total) / prev_total
        else:
            delta = None if cur_total == 0 else float("inf")

        promised = promised_by_user.get(r.id, 0)
        paid = paid_by_user.get(r.id, 0)
        items.append(
            TeamPerformanceItem(
                user_id=r.id,
                name=r.name,
                total_calls=cur_total,
                connected_calls=cur_conn,
                promised_cases=promised,
                paid_cases=paid,
                conversion_rate=(promised / cur_total) if cur_total else None,
                delta_vs_previous=None if delta == float("inf") else delta,
            )
        )
    items.sort(key=lambda x: x.total_calls, reverse=True)
    return TeamPerformanceOut(period_days=period_days, items=items)
