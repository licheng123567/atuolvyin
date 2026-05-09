"""Case timeline aggregator — merges events from multiple tables for a single case.

Used by both admin/cases/{id} and agent/cases/{id} detail endpoints.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.call import CallRecord
from app.models.legal_conversion import LegalConversionOrder
from app.models.user import UserAccount
from app.models.work import LegalCase, WorkOrder
from app.schemas.case import TimelineEvent


def build_case_timeline(
    db: Session,
    case_id: int,
    tenant_id: int,
) -> list[TimelineEvent]:
    """Aggregate events that touch this case. Sorted desc by ts."""

    events: list[TimelineEvent] = []

    # ── 通话 ─────────────────────────────────────────────────────
    call_rows = db.execute(
        select(CallRecord, UserAccount.name)
        .join(UserAccount, UserAccount.id == CallRecord.caller_user_id, isouter=True)
        .where(CallRecord.case_id == case_id, CallRecord.tenant_id == tenant_id)
    ).all()
    for call, agent_name in call_rows:
        ts = call.started_at or call.created_at
        if ts is None:
            continue
        result = call.result_tag or call.status
        events.append(
            TimelineEvent(
                type="call",
                ts=ts,
                actor=agent_name,
                note=f"通话 · {result}",
            )
        )

    # ── 工单 ─────────────────────────────────────────────────────
    wo_rows = db.execute(
        select(WorkOrder, UserAccount.name)
        .join(UserAccount, UserAccount.id == WorkOrder.assigned_to, isouter=True)
        .where(WorkOrder.case_id == case_id, WorkOrder.tenant_id == tenant_id)
    ).all()
    for wo, assignee_name in wo_rows:
        events.append(
            TimelineEvent(
                type="workorder.opened",
                ts=wo.created_at,
                actor=assignee_name,
                note=f"工单 [{wo.order_type}] {wo.description[:80]}",
                target_id=wo.id,
                target_type="workorder",
            )
        )
        if wo.status in ("resolved", "closed") and wo.updated_at != wo.created_at:
            events.append(
                TimelineEvent(
                    type="workorder.resolved",
                    ts=wo.updated_at,
                    actor=assignee_name,
                    note=f"工单已处理 · {wo.resolution[:80] if wo.resolution else wo.status}",
                    target_id=wo.id,
                    target_type="workorder",
                )
            )

    # ── 法务转化 ─────────────────────────────────────────────────
    lc_rows = db.execute(
        select(LegalConversionOrder).where(
            LegalConversionOrder.case_id == case_id,
            LegalConversionOrder.tenant_id == tenant_id,
        )
    ).scalars().all()
    for lc in lc_rows:
        events.append(
            TimelineEvent(
                type="legal.converted",
                ts=lc.created_at,
                actor=None,
                note=f"转化为法务案件 · {lc.status}",
                target_id=lc.id,
                target_type="legal_order",
            )
        )

    # ── 法务案件状态 ────────────────────────────────────────────
    legal_cases = db.execute(
        select(LegalCase).where(
            LegalCase.case_id == case_id,
            LegalCase.tenant_id == tenant_id,
        )
    ).scalars().all()
    for lc in legal_cases:
        events.append(
            TimelineEvent(
                type="legal.case",
                ts=lc.created_at,
                actor=lc.lawyer_name,
                note=f"法务跟进 · {lc.stage}" + (f" ({lc.next_milestone})" if lc.next_milestone else ""),
                target_id=lc.id,
                target_type="legal_case",
            )
        )

    # ── 阶段 / 分配审计 ─────────────────────────────────────────
    audit_rows = db.execute(
        select(AuditLog, UserAccount.name)
        .join(UserAccount, UserAccount.id == AuditLog.actor_user_id, isouter=True)
        .where(
            AuditLog.target_type == "case",
            AuditLog.target_id == case_id,
            AuditLog.tenant_id == tenant_id,
            AuditLog.action.in_(
                ("case.assigned", "case.stage_changed", "case.escalated", "case.released")
            ),
        )
    ).all()
    for log, actor_name in audit_rows:
        note = log.action
        if log.payload:
            payload = log.payload
            if log.action == "case.assigned" and "assignee_name" in payload:
                note = f"分配给 {payload['assignee_name']}"
            elif log.action == "case.stage_changed" and "stage" in payload:
                note = f"阶段更新 → {payload['stage']}"
            elif log.action == "case.escalated":
                note = "升级处理"
            elif log.action == "case.released":
                note = "释放至公海"
        events.append(
            TimelineEvent(
                type=log.action,
                ts=log.created_at,
                actor=actor_name,
                note=note,
            )
        )

    events.sort(key=_event_ts, reverse=True)
    return events


def _event_ts(e: TimelineEvent) -> datetime:
    return e.ts
