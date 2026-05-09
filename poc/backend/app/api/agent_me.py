"""Sprint 11.4 — Agent personal performance dashboard (PRD §5B / L2099).

PC view (App side handled in Android Sprint 11.5/.7/.9). Returns the current
month's calls / connected / promised / paid + minute quota usage + tenant rank.
"""
from __future__ import annotations

from datetime import UTC, date as date_type, datetime, time
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
import sqlalchemy as sa
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.call import AnalysisResult, CallRecord, Transcript
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.tenant import Tenant, TenantMinuteUsage
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
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


# ── v1.6.5 — 催收员通话记录 ─────────────────────────────────────
class CallHistoryItem(BaseModel):
    call_id: int
    started_at: datetime | None
    duration_sec: int | None
    result_tag: str | None
    case_id: int | None
    owner_name: str | None
    building: str | None
    room: str | None
    project_id: int | None
    project_name: str | None
    has_transcript: bool
    has_analysis: bool
    recording_url: str | None = None  # v1.6.7 — E5 inline 录音
    score: int | None = None           # v1.6.7 — E6 综合评分（0-100）


@router.get("/me/call-history", response_model=PaginatedResponse[CallHistoryItem])
def list_my_call_history(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    date_from: Annotated[date_type | None, Query()] = None,
    date_to: Annotated[date_type | None, Query()] = None,
    result: Annotated[str | None, Query(description="result_tag 包含匹配")] = None,
    project_id: Annotated[int | None, Query()] = None,
    q: Annotated[str | None, Query(description="业主姓名 / 楼栋 / 房号")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[CallHistoryItem]:
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )

    stmt = (
        select(CallRecord, OwnerProfile, Project)
        .join(CollectionCase, CollectionCase.id == CallRecord.case_id, isouter=True)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id, isouter=True)
        .join(Project, Project.id == CollectionCase.project_id, isouter=True)
        .where(
            CallRecord.tenant_id == tenant_id,
            CallRecord.caller_user_id == user_id,
        )
    )
    if date_from is not None:
        stmt = stmt.where(CallRecord.started_at >= datetime.combine(date_from, time.min, UTC))
    if date_to is not None:
        stmt = stmt.where(CallRecord.started_at < datetime.combine(date_to, time.max, UTC))
    if result and result.strip():
        stmt = stmt.where(CallRecord.result_tag.ilike(f"%{result.strip()}%"))
    if project_id is not None:
        stmt = stmt.where(CollectionCase.project_id == project_id)
    if q and q.strip():
        kw = f"%{q.strip()}%"
        stmt = stmt.where(
            sa.or_(
                OwnerProfile.name.ilike(kw),
                OwnerProfile.building.ilike(kw),
                OwnerProfile.room.ilike(kw),
            )
        )

    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(CallRecord.started_at.desc().nulls_last(), CallRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    # Batch lookup transcript / analysis presence
    call_ids = [r[0].id for r in rows]
    transcript_ids: set[int] = set()
    analysis_ids: set[int] = set()
    if call_ids:
        transcript_ids = {
            cid for (cid,) in db.execute(
                select(Transcript.call_id).where(Transcript.call_id.in_(call_ids))
            ).all()
        }
        analysis_ids = {
            cid for (cid,) in db.execute(
                select(AnalysisResult.call_id).where(AnalysisResult.call_id.in_(call_ids))
            ).all()
        }

    items: list[CallHistoryItem] = []
    for cr, owner, proj in rows:
        # v1.6.7 — E6 mock 评分（仅对接通过的通话）
        call_score: int | None = None
        if cr.billable_duration and cr.billable_duration > 0:
            call_score = _mock_score_for_call(cr.id).score
        items.append(CallHistoryItem(
            call_id=cr.id,
            started_at=cr.started_at,
            duration_sec=cr.duration_sec,
            result_tag=cr.result_tag,
            case_id=cr.case_id,
            owner_name=owner.name if owner else None,
            building=owner.building if owner else None,
            room=owner.room if owner else None,
            project_id=proj.id if proj else None,
            project_name=proj.name if proj else None,
            has_transcript=cr.id in transcript_ids,
            has_analysis=cr.id in analysis_ids,
            recording_url=cr.recording_url,
            score=call_score,
        ))

    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


# ── v1.6.7 — E2 今日 KPI 进度条 ─────────────────────────────────
class TodayKpiResp(BaseModel):
    date: str                  # YYYY-MM-DD
    calls_today: int            # 今日拨号数
    calls_target: int           # 今日目标（默认 30，PoC 阶段写死）
    connected_today: int        # 今日接通数
    promised_today: int         # 今日新增承诺数
    paid_today: int             # 今日新增缴清数
    minutes_used_today: int     # 今日通话分钟数


@router.get("/me/today-kpi", response_model=TodayKpiResp)
def get_my_today_kpi(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TodayKpiResp:
    """工作台顶部 KPI 进度条数据源。"""
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    call_row = db.execute(
        sa.select(
            sa.func.count().label("total"),
            sa.func.coalesce(sa.func.sum(
                sa.case((CallRecord.billable_duration > 0, 1), else_=0)
            ), 0).label("connected"),
            sa.func.coalesce(sa.func.sum(CallRecord.billable_duration), 0).label("billable"),
        )
        .where(CallRecord.tenant_id == tenant_id)
        .where(CallRecord.caller_user_id == user_id)
        .where(CallRecord.created_at >= today_start)
    ).first()

    promised_today = (
        db.execute(
            sa.select(sa.func.count())
            .select_from(CollectionCase)
            .where(CollectionCase.tenant_id == tenant_id)
            .where(CollectionCase.assigned_to == user_id)
            .where(CollectionCase.stage == "promised")
            .where(CollectionCase.updated_at >= today_start)
        ).scalar_one() or 0
    )
    paid_today = (
        db.execute(
            sa.select(sa.func.count())
            .select_from(CollectionCase)
            .where(CollectionCase.tenant_id == tenant_id)
            .where(CollectionCase.assigned_to == user_id)
            .where(CollectionCase.stage == "paid")
            .where(CollectionCase.updated_at >= today_start)
        ).scalar_one() or 0
    )

    return TodayKpiResp(
        date=today_start.strftime("%Y-%m-%d"),
        calls_today=int(call_row.total or 0),
        calls_target=30,
        connected_today=int(call_row.connected or 0),
        promised_today=int(promised_today),
        paid_today=int(paid_today),
        minutes_used_today=int((call_row.billable or 0) // 60),
    )


# ── v1.6.7 — E6 通话评分趋势（mock，PoC 阶段不连真 LLM） ────────
class CallScoreItem(BaseModel):
    call_id: int
    score: int           # 0-100 综合得分
    talk: int            # 话术
    emotion: int         # 情绪
    conversion: int      # 转化


class ScoringTrendResp(BaseModel):
    avg_score_30d: int
    avg_talk: int
    avg_emotion: int
    avg_conversion: int
    recent: list[CallScoreItem]


def _mock_score_for_call(call_id: int) -> CallScoreItem:
    """v1.6.7 — PoC 评分生成器（deterministic by call_id；后续替换为 LLM 调用）。"""
    seed = call_id * 2654435761 & 0xffffffff
    talk = 60 + (seed % 35)
    emotion = 55 + ((seed >> 8) % 40)
    conversion = 50 + ((seed >> 16) % 45)
    score = (talk + emotion + conversion) // 3
    return CallScoreItem(call_id=call_id, score=score, talk=talk, emotion=emotion, conversion=conversion)


@router.get("/me/scoring-trend", response_model=ScoringTrendResp)
def get_my_scoring_trend(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ScoringTrendResp:
    """近 30 天通话评分（PoC 阶段使用 mock 算法）。"""
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )
    from datetime import timedelta
    cutoff = datetime.now(UTC) - timedelta(days=30)
    recent_call_ids = [
        cid for (cid,) in db.execute(
            sa.select(CallRecord.id)
            .where(CallRecord.tenant_id == tenant_id)
            .where(CallRecord.caller_user_id == user_id)
            .where(CallRecord.created_at >= cutoff)
            .where(CallRecord.billable_duration > 0)
            .order_by(CallRecord.created_at.desc())
            .limit(50)
        ).all()
    ]
    items = [_mock_score_for_call(cid) for cid in recent_call_ids]
    if not items:
        return ScoringTrendResp(avg_score_30d=0, avg_talk=0, avg_emotion=0, avg_conversion=0, recent=[])
    return ScoringTrendResp(
        avg_score_30d=sum(i.score for i in items) // len(items),
        avg_talk=sum(i.talk for i in items) // len(items),
        avg_emotion=sum(i.emotion for i in items) // len(items),
        avg_conversion=sum(i.conversion for i in items) // len(items),
        recent=items[:10],
    )


# ── v1.6.5 — App→PC 同步：催收员当前 active call ──────────────
class ActiveCallResp(BaseModel):
    active_call_id: int | None
    case_id: int | None
    started_at: datetime | None
    status: str | None
    owner_name: str | None
    owner_phone_masked: str | None
    building: str | None
    room: str | None
    amount_owed: Decimal | None
    project_id: int | None
    project_name: str | None


@router.get("/me/active-call", response_model=ActiveCallResp)
def get_my_active_call(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ActiveCallResp:
    """工作台轮询：返回当前催收员名下处于 dialing/live 状态的通话。

    PC 端工作台每 5s 查询一次；命中时自动切到 RealtimeCallShell（接 WS）。
    使用与督导通话墙 (`supervisor/live-calls`) 相同的状态判定。
    """
    from app.core.crypto import mask_phone

    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )

    call = db.execute(
        select(CallRecord)
        .where(
            CallRecord.tenant_id == tenant_id,
            CallRecord.caller_user_id == user_id,
            CallRecord.status.in_(("dialing", "live")),
        )
        .order_by(CallRecord.started_at.desc().nulls_last())
        .limit(1)
    ).scalar_one_or_none()

    if call is None:
        return ActiveCallResp(
            active_call_id=None, case_id=None, started_at=None, status=None,
            owner_name=None, owner_phone_masked=None, building=None, room=None,
            amount_owed=None, project_id=None, project_name=None,
        )

    case = db.get(CollectionCase, call.case_id) if call.case_id else None
    owner = db.get(OwnerProfile, case.owner_id) if case and case.owner_id else None
    project = db.get(Project, case.project_id) if case and case.project_id else None

    return ActiveCallResp(
        active_call_id=call.id,
        case_id=call.case_id,
        started_at=call.started_at,
        status=call.status,
        owner_name=owner.name if owner else None,
        owner_phone_masked=mask_phone(owner.phone_enc) if owner and owner.phone_enc else None,
        building=owner.building if owner else None,
        room=owner.room if owner else None,
        amount_owed=case.amount_owed if case else None,
        project_id=project.id if project else None,
        project_name=project.name if project else None,
    )
