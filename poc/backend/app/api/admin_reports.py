"""Sprint 8.3 — Admin reports (PRD §3.12 / L2047).

物业管理员的数据报表：
  - 转化漏斗（CollectionCase 当前 stage 分布）
  - 员工效率（每个坐席通话/接通/承诺/转化率）
  - 异议类型分布（基于 SuggestionFeedback → ScriptTemplate.trigger_intent）
  - 承诺跟进完成率（promised → paid 的占比，基于当前 stage 推估）

注：CollectionCase 没有 stage 变更日志，所以漏斗与跟进完成率是「快照」语义，
而非「在窗内进入该 stage 的案件数」。这是已知简化，未来可补 case_stage_history 表。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_tenant_roles
from app.models.call import CallRecord, SuggestionFeedback
from app.models.case import CollectionCase
from app.models.script import ScriptTemplate
from app.models.user import UserAccount
from app.schemas.report import (
    AgentPerformanceOut,
    FunnelStageOut,
    ObjectionItemOut,
    PromiseFollowupOut,
    ReportOverviewOut,
)

router = APIRouter()

ADMIN_ROLES = ("admin", "superadmin")

FUNNEL_STAGES: list[tuple[str, str]] = [
    ("new", "新案"),
    ("contacted", "已联系"),
    ("promised", "承诺缴费"),
    ("paid", "已缴费"),
    ("closed", "已关闭"),
]


@router.get("/reports/overview", response_model=ReportOverviewOut)
def report_overview(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    period_days: int = Query(30, ge=1, le=365),
) -> ReportOverviewOut:
    tenant_id = int(payload.get("tenant_id") or 0)
    cutoff = datetime.now(UTC) - timedelta(days=period_days)

    # ── Funnel — case count per stage (snapshot, not event-based) ──
    stage_rows = db.execute(
        select(CollectionCase.stage, func.count())
        .where(CollectionCase.tenant_id == tenant_id)
        .group_by(CollectionCase.stage)
    ).all()
    stage_counts: dict[str, int] = {s: int(c) for s, c in stage_rows}
    funnel = [
        FunnelStageOut(stage=stage, label=label, count=stage_counts.get(stage, 0))
        for stage, label in FUNNEL_STAGES
    ]

    # ── Agent performance — calls in window grouped by caller ──
    agent_rows = db.execute(
        select(
            UserAccount.id,
            UserAccount.name,
            func.count(CallRecord.id).label("total_calls"),
            func.sum(case((CallRecord.billable_duration > 0, 1), else_=0)).label("connected_calls"),
        )
        .join(CallRecord, CallRecord.caller_user_id == UserAccount.id)
        .where(CallRecord.tenant_id == tenant_id)
        .where(CallRecord.created_at >= cutoff)
        .group_by(UserAccount.id, UserAccount.name)
        .order_by(func.count(CallRecord.id).desc())
        .limit(50)
    ).all()

    user_ids = [r.id for r in agent_rows]
    promised_rows = (
        db.execute(
            select(CollectionCase.assigned_to, func.count())
            .where(CollectionCase.tenant_id == tenant_id)
            .where(CollectionCase.assigned_to.in_(user_ids))
            .where(CollectionCase.stage == "promised")
            .group_by(CollectionCase.assigned_to)
        ).all()
        if user_ids
        else []
    )
    promised_by_user: dict[int, int] = {uid: int(c) for uid, c in promised_rows}

    agent_performance = [
        AgentPerformanceOut(
            user_id=r.id,
            name=r.name,
            total_calls=int(r.total_calls or 0),
            connected_calls=int(r.connected_calls or 0),
            promised_cases=promised_by_user.get(r.id, 0),
            conversion_rate=(
                promised_by_user.get(r.id, 0) / r.total_calls if r.total_calls else None
            ),
        )
        for r in agent_rows
    ]

    # ── Objection distribution — SuggestionFeedback grouped by template intent ──
    objection_rows = db.execute(
        select(ScriptTemplate.trigger_intent, func.count(SuggestionFeedback.id))
        .join(
            SuggestionFeedback,
            SuggestionFeedback.script_template_id == ScriptTemplate.id,
        )
        .join(CallRecord, CallRecord.id == SuggestionFeedback.call_id)
        .where(CallRecord.tenant_id == tenant_id)
        .where(SuggestionFeedback.created_at >= cutoff)
        .group_by(ScriptTemplate.trigger_intent)
        .order_by(func.count(SuggestionFeedback.id).desc())
    ).all()
    objection_distribution = [
        ObjectionItemOut(intent=intent, count=int(count)) for intent, count in objection_rows
    ]

    # ── Promise → Paid follow-up rate (snapshot) ──
    total_promised = (
        db.execute(
            select(func.count())
            .select_from(CollectionCase)
            .where(CollectionCase.tenant_id == tenant_id)
            .where(CollectionCase.stage.in_(("promised", "paid")))
        ).scalar_one()
        or 0
    )
    total_paid = (
        db.execute(
            select(func.count())
            .select_from(CollectionCase)
            .where(CollectionCase.tenant_id == tenant_id)
            .where(CollectionCase.stage == "paid")
        ).scalar_one()
        or 0
    )
    promise_followup = PromiseFollowupOut(
        total_promised=int(total_promised),
        total_paid=int(total_paid),
        rate=(int(total_paid) / int(total_promised)) if total_promised else None,
    )

    return ReportOverviewOut(
        period_days=period_days,
        funnel=funnel,
        agent_performance=agent_performance,
        objection_distribution=objection_distribution,
        promise_followup=promise_followup,
    )
