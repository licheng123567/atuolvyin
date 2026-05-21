"""Sprint 11.4 — Agent personal performance dashboard (PRD §5B / L2099).

PC view (App side handled in Android Sprint 11.5/.7/.9). Returns the current
month's calls / connected / promised / paid + minute quota usage + tenant rank.
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from datetime import date as date_type
from decimal import Decimal
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.call import AnalysisResult, CallRecord, Transcript
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.tenant import Tenant, TenantMinuteUsage
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse

router = APIRouter()

AGENT_ROLES = ("agent",)


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
    score: int | None = None  # v1.6.7 — E6 综合评分（0-100）


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
            cid
            for (cid,) in db.execute(
                select(Transcript.call_id).where(Transcript.call_id.in_(call_ids))
            ).all()
        }
        analysis_ids = {
            cid
            for (cid,) in db.execute(
                select(AnalysisResult.call_id).where(AnalysisResult.call_id.in_(call_ids))
            ).all()
        }

    items: list[CallHistoryItem] = []
    for cr, owner, proj in rows:
        # v1.6.7 — E6 mock 评分（仅对接通过的通话）
        call_score: int | None = None
        if cr.billable_duration and cr.billable_duration > 0:
            call_score = _mock_score_for_call(cr.id).score
        items.append(
            CallHistoryItem(
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
            )
        )

    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


# ── v1.6.7 — E2 今日 KPI 进度条 ─────────────────────────────────
class TodayKpiResp(BaseModel):
    date: str  # YYYY-MM-DD
    calls_today: int  # 今日拨号数
    calls_target: int  # 今日目标（默认 30，PoC 阶段写死）
    connected_today: int  # 今日接通数
    promised_today: int  # 今日新增承诺数
    paid_today: int  # 今日新增缴清数
    minutes_used_today: int  # 今日通话分钟数


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
            sa.func.coalesce(
                sa.func.sum(sa.case((CallRecord.billable_duration > 0, 1), else_=0)), 0
            ).label("connected"),
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
        ).scalar_one()
        or 0
    )
    paid_today = (
        db.execute(
            sa.select(sa.func.count())
            .select_from(CollectionCase)
            .where(CollectionCase.tenant_id == tenant_id)
            .where(CollectionCase.assigned_to == user_id)
            .where(CollectionCase.stage == "paid")
            .where(CollectionCase.updated_at >= today_start)
        ).scalar_one()
        or 0
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


# ── v0.6.0 — 催收员按项目维度的本月统计 ────────────────────────
class AgentProjectStatsItem(BaseModel):
    project_id: int
    project_name: str
    case_count: int  # 我接的本项目案件数(私海)
    paid_case_count: int  # 本月已回款案件数
    recovered_amount: Decimal  # 本月已回款金额(amount_owed 之和,stage='paid')
    estimated_commission: Decimal  # 预估佣金 = recovered_amount * project rate(按 work_mode)
    commission_rate_pct: float | None  # 用了哪个 rate(0.0-1.0),便于排查


class AgentProjectStatsResp(BaseModel):
    year_month: str
    work_mode: str | None  # 当前 agent 的 work_mode(internal / external)
    items: list[AgentProjectStatsItem]
    total_recovered_amount: Decimal
    total_estimated_commission: Decimal


@router.get("/me/by-project", response_model=AgentProjectStatsResp)
def get_my_by_project(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$", description="YYYY-MM,默认本月"),
) -> AgentProjectStatsResp:
    """工作台底部「我的项目」卡片网格 — 按项目维度统计案件/回款/预估佣金。

    估算佣金:
      - 本月 stage='paid' 且 assigned_to=me 的案件 amount_owed 汇总
      - 乘以 project.internal_agent_commission_rate(work_mode=internal)
        或 project.provider_agent_commission_rate(work_mode=external)
      - 该项目没设对应费率时显示 NULL 不计入合计
    """
    from app.models.tenant import UserTenantMembership

    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )

    # 本月窗口
    now = datetime.now(UTC)
    if month:
        year, mon = month.split("-")
        ym = f"{year}-{mon}"
        month_start = datetime(int(year), int(mon), 1, tzinfo=UTC)
        next_mon = month_start.replace(
            year=month_start.year + (1 if month_start.month == 12 else 0),
            month=1 if month_start.month == 12 else month_start.month + 1,
        )
    else:
        ym = now.strftime("%Y-%m")
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_mon = month_start.replace(
            year=month_start.year + (1 if month_start.month == 12 else 0),
            month=1 if month_start.month == 12 else month_start.month + 1,
        )

    # 当前催收员的 work_mode(决定走 internal/external commission rate)
    membership = db.execute(
        select(UserTenantMembership)
        .where(UserTenantMembership.user_id == user_id)
        .where(UserTenantMembership.tenant_id == tenant_id)
        .where(UserTenantMembership.role == "agent")
        .limit(1)
    ).scalar_one_or_none()
    work_mode = membership.work_mode if membership else None

    # 1. 我接的所有有项目归属的案件分组:case_count + paid_case_count + recovered_amount
    rows = db.execute(
        select(
            CollectionCase.project_id,
            Project.name.label("project_name"),
            func.count(CollectionCase.id).label("case_count"),
            func.sum(case((CollectionCase.stage == "paid"), else_=None)).label(
                "paid_marker"
            ),  # 仅用于辅助
            func.count(
                case(
                    (
                        (CollectionCase.stage == "paid")
                        & (CollectionCase.updated_at >= month_start)
                        & (CollectionCase.updated_at < next_mon),
                        CollectionCase.id,
                    )
                )
            ).label("paid_case_count"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (CollectionCase.stage == "paid")
                            & (CollectionCase.updated_at >= month_start)
                            & (CollectionCase.updated_at < next_mon),
                            CollectionCase.amount_owed,
                        ),
                        else_=Decimal("0"),
                    )
                ),
                Decimal("0"),
            ).label("recovered_amount"),
            Project.internal_agent_commission_rate,
            Project.provider_agent_commission_rate,
        )
        .join(Project, Project.id == CollectionCase.project_id)
        .where(CollectionCase.tenant_id == tenant_id)
        .where(CollectionCase.assigned_to == user_id)
        .where(CollectionCase.project_id.isnot(None))
        .group_by(
            CollectionCase.project_id,
            Project.name,
            Project.internal_agent_commission_rate,
            Project.provider_agent_commission_rate,
        )
        .order_by(func.count(CollectionCase.id).desc())
    ).all()

    items: list[AgentProjectStatsItem] = []
    total_recovered = Decimal("0")
    total_commission = Decimal("0")
    for r in rows:
        if work_mode == "internal":
            rate = r.internal_agent_commission_rate
        elif work_mode == "external":
            rate = r.provider_agent_commission_rate
        else:
            rate = None

        recovered = Decimal(r.recovered_amount or 0)
        commission = (
            (recovered * rate).quantize(Decimal("0.01")) if rate is not None else Decimal("0")
        )

        items.append(
            AgentProjectStatsItem(
                project_id=int(r.project_id),
                project_name=str(r.project_name or "—"),
                case_count=int(r.case_count or 0),
                paid_case_count=int(r.paid_case_count or 0),
                recovered_amount=recovered,
                estimated_commission=commission,
                commission_rate_pct=float(rate) if rate is not None else None,
            )
        )
        total_recovered += recovered
        if rate is not None:
            total_commission += commission

    return AgentProjectStatsResp(
        year_month=ym,
        work_mode=work_mode,
        items=items,
        total_recovered_amount=total_recovered.quantize(Decimal("0.01")),
        total_estimated_commission=total_commission.quantize(Decimal("0.01")),
    )


# ── v0.6.0 — 催收员提醒中心:整合 promise 到期 / 法务状态 / 案件 SLA 三类 ────
class ReminderPromiseDueItem(BaseModel):
    case_id: int
    owner_name: str
    building_room: str
    promise_due_at: datetime
    promise_amount: Decimal | None
    promise_content: str | None
    hours_to_due: float


class ReminderLegalStatusItem(BaseModel):
    request_id: int
    case_id: int
    owner_name: str
    status: str
    reviewer_note: str | None
    updated_at: datetime


class ReminderCaseSlaItem(BaseModel):
    case_id: int
    owner_name: str
    building_room: str
    last_contact_at: datetime | None
    days_stuck: int  # 案件 stage 停留天数(updated_at 计算)
    amount_owed: Decimal | None


class ReminderSyntheticOut(BaseModel):
    """GET /agent/me/reminders/synthetic 响应 — 3 类「软提醒」整合。

    与 Notification 表正交:此处的数据是「实时计算的状态提醒」,
    没有读 / 未读语义(不靠用户 click 消失);Notification 是事件类的硬通知。
    """

    promise_due_soon: list[ReminderPromiseDueItem]
    legal_status_changes: list[ReminderLegalStatusItem]
    case_sla_warn: list[ReminderCaseSlaItem]


@router.get("/me/reminders/synthetic", response_model=ReminderSyntheticOut)
def get_my_reminders_synthetic(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    promise_window_hours: int = Query(72, ge=1, le=168),
    sla_stuck_days: int = Query(30, ge=7, le=365),
) -> ReminderSyntheticOut:
    """催收员提醒中心数据源 — 3 类软提醒。

    1. promise_due_soon:promise_due_at 在未来 N 小时内的案件
       (默认 72h,与 PROMISE_EXPIRING 任务的 24h 窗口互补 — 这里更宽,展示「即将」)
    2. legal_status_changes:近 7 天该催收员发起的 LegalConversionRequest 状态变化
       (approved / rejected / approved_pending_legal)
    3. case_sla_warn:catch_all,assigned_to=me 且 updated_at < now - 30d 且 stage 非终止态
    """
    from datetime import timedelta

    from app.models.legal_conversion import LegalConversionRequest

    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )

    now = datetime.now(UTC)
    promise_until = now + timedelta(hours=promise_window_hours)
    sla_cutoff = now - timedelta(days=sla_stuck_days)
    legal_cutoff = now - timedelta(days=7)

    # ① promise 即将到期
    promise_rows = db.execute(
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(CollectionCase.tenant_id == tenant_id)
        .where(CollectionCase.assigned_to == user_id)
        .where(CollectionCase.promise_due_at.isnot(None))
        .where(CollectionCase.promise_due_at <= promise_until)
        .where(CollectionCase.promise_due_at > now)
        .where(CollectionCase.stage != "paid")
        .order_by(CollectionCase.promise_due_at.asc())
        .limit(50)
    ).all()
    promise_items = [
        ReminderPromiseDueItem(
            case_id=case.id,
            owner_name=owner.name,
            building_room=(owner.building or "") + (owner.room or ""),
            promise_due_at=case.promise_due_at,
            promise_amount=case.promise_amount,
            promise_content=case.promise_content,
            hours_to_due=round((case.promise_due_at - now).total_seconds() / 3600.0, 1),
        )
        for case, owner in promise_rows
    ]

    # ② 法务申请状态变化(本催收员提交的,近 7 天有更新)
    legal_rows = db.execute(
        select(LegalConversionRequest, OwnerProfile)
        .join(CollectionCase, CollectionCase.id == LegalConversionRequest.case_id)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(LegalConversionRequest.tenant_id == tenant_id)
        .where(LegalConversionRequest.requester_user_id == user_id)
        .where(LegalConversionRequest.updated_at >= legal_cutoff)
        .where(
            LegalConversionRequest.status.in_(("approved", "rejected", "approved_pending_legal"))
        )
        .order_by(LegalConversionRequest.updated_at.desc())
        .limit(20)
    ).all()
    legal_items = [
        ReminderLegalStatusItem(
            request_id=req.id,
            case_id=req.case_id,
            owner_name=owner.name,
            status=req.status,
            reviewer_note=req.reviewer_note,
            updated_at=req.updated_at,
        )
        for req, owner in legal_rows
    ]

    # ③ 案件 SLA 告警 — 停滞 > N 天的非终止案件
    sla_rows = db.execute(
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(CollectionCase.tenant_id == tenant_id)
        .where(CollectionCase.assigned_to == user_id)
        .where(CollectionCase.updated_at < sla_cutoff)
        .where(
            CollectionCase.stage.notin_(
                ("paid", "closed", "uncollectible", "pending_close", "legal")
            )
        )
        .order_by(CollectionCase.updated_at.asc())
        .limit(30)
    ).all()
    sla_items = [
        ReminderCaseSlaItem(
            case_id=case.id,
            owner_name=owner.name,
            building_room=(owner.building or "") + (owner.room or ""),
            last_contact_at=case.last_contact_at,
            days_stuck=int((now - case.updated_at).days),
            amount_owed=case.amount_owed,
        )
        for case, owner in sla_rows
    ]

    return ReminderSyntheticOut(
        promise_due_soon=promise_items,
        legal_status_changes=legal_items,
        case_sla_warn=sla_items,
    )


# ── v1.6.7 — E6 通话评分趋势（mock，PoC 阶段不连真 LLM） ────────
class CallScoreItem(BaseModel):
    call_id: int
    score: int  # 0-100 综合得分
    talk: int  # 话术
    emotion: int  # 情绪
    conversion: int  # 转化


class ScoringTrendResp(BaseModel):
    avg_score_30d: int
    avg_talk: int
    avg_emotion: int
    avg_conversion: int
    recent: list[CallScoreItem]


def _mock_score_for_call(call_id: int) -> CallScoreItem:
    """v1.6.7 — PoC 评分生成器（deterministic by call_id；后续替换为 LLM 调用）。"""
    seed = call_id * 2654435761 & 0xFFFFFFFF
    talk = 60 + (seed % 35)
    emotion = 55 + ((seed >> 8) % 40)
    conversion = 50 + ((seed >> 16) % 45)
    score = (talk + emotion + conversion) // 3
    return CallScoreItem(
        call_id=call_id, score=score, talk=talk, emotion=emotion, conversion=conversion
    )


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
        cid
        for (cid,) in db.execute(
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
        return ScoringTrendResp(
            avg_score_30d=0, avg_talk=0, avg_emotion=0, avg_conversion=0, recent=[]
        )
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
    from app.core.phone_visibility import (
        display_owner_phone,
        is_provider_contract_active,
        should_reveal_owner_phone,
    )

    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    role = payload.get("role", "")
    contract_active = is_provider_contract_active(db, tenant_id, payload.get("provider_id"))
    owner_phone_reveal = should_reveal_owner_phone(
        role=role, provider_id=payload.get("provider_id"), contract_active=contract_active
    )
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
            active_call_id=None,
            case_id=None,
            started_at=None,
            status=None,
            owner_name=None,
            owner_phone_masked=None,
            building=None,
            room=None,
            amount_owed=None,
            project_id=None,
            project_name=None,
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
        owner_phone_masked=display_owner_phone(
            owner.phone_enc if owner else None,
            reveal=owner_phone_reveal,
        ),
        building=owner.building if owner else None,
        room=owner.room if owner else None,
        amount_owed=case.amount_owed if case else None,
        project_id=project.id if project else None,
        project_name=project.name if project else None,
    )


# ── v0.7.0 — 催收员侧培训案例库浏览(只读;PC + App WebView 共用) ────────
class AgentTrainingCaseItem(BaseModel):
    """与 supervisor_training.TrainingCaseOut 字段对齐;只读 — 不返回 created_by 等内部字段。"""

    id: int
    title: str
    category: str
    scenario: str
    lesson: str
    raw_call_id: int | None
    rating: int
    views: int
    source: str
    created_at: datetime


class AgentTrainingListResp(BaseModel):
    items: list[AgentTrainingCaseItem]
    total: int


@router.get("/me/training-cases", response_model=AgentTrainingListResp)
def list_my_training_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    category: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
) -> AgentTrainingListResp:
    """催收员浏览本租户培训案例库(只读)。

    范围:本租户 training_case(由本租户督导沉淀);跨租户不开放。
    `view_count` 由配套 POST `/me/training-cases/{id}/view` 累加。
    """
    from app.models.training_case import TrainingCase

    tenant_id = int(payload.get("tenant_id") or 0)
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )

    stmt = sa.select(TrainingCase).where(TrainingCase.tenant_id == tenant_id)
    if category:
        stmt = stmt.where(TrainingCase.category == category)

    total = db.execute(
        sa.select(sa.func.count(TrainingCase.id))
        .where(TrainingCase.tenant_id == tenant_id)
        .where(TrainingCase.category == category if category else sa.true())
    ).scalar_one()

    rows = (
        db.execute(
            stmt.order_by(TrainingCase.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    return AgentTrainingListResp(
        items=[
            AgentTrainingCaseItem(
                id=r.id,
                title=r.title,
                category=r.category,
                scenario=r.scenario,
                lesson=r.lesson,
                raw_call_id=r.raw_call_id,
                rating=r.rating,
                views=r.views,
                source=r.source,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=int(total or 0),
    )


@router.post("/me/training-cases/{tc_id}/view", response_model=AgentTrainingCaseItem)
def view_training_case(
    tc_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> AgentTrainingCaseItem:
    """催收员点开案例时调一次,+1 view 计数。返回案例详情。"""
    from app.models.training_case import TrainingCase

    tenant_id = int(payload.get("tenant_id") or 0)
    tc = db.get(TrainingCase, tc_id)
    if tc is None or tc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "培训案例不存在"},
        )

    tc.views = (tc.views or 0) + 1
    db.commit()
    db.refresh(tc)

    return AgentTrainingCaseItem(
        id=tc.id,
        title=tc.title,
        category=tc.category,
        scenario=tc.scenario,
        lesson=tc.lesson,
        raw_call_id=tc.raw_call_id,
        rating=tc.rating,
        views=tc.views,
        source=tc.source,
        created_at=tc.created_at,
    )
