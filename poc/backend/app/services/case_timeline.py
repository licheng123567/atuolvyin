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
from app.models.legal_internal import (
    InternalLegalLetterTemplate,
    LegalInternalAction,
    PartnerLawFirm,
)
from app.models.user import UserAccount
from app.models.work import LegalCase, WorkOrder
from app.schemas.case import TimelineEvent

# v1.9.0 — 物业内部法务 action_type → timeline event type 映射
_INTERNAL_ACTION_TYPE_MAP = {
    "contact_owner": "legal.internal.contact_owner",
    "send_lawyer_letter": "legal.internal.send_lawyer_letter",
    "send_notice": "legal.internal.send_notice",
    "mediation": "legal.internal.mediation",
    "other": "legal.internal.other",
}


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
        if wo.status == "resolved" and wo.updated_at != wo.created_at:
            events.append(
                TimelineEvent(
                    type="workorder.resolved",
                    ts=wo.updated_at,
                    actor=assignee_name,
                    note=f"工单已解决 · {wo.resolution[:80] if wo.resolution else '已完成'}",
                    target_id=wo.id,
                    target_type="workorder",
                )
            )
        elif wo.status == "closed" and wo.updated_at != wo.created_at:
            events.append(
                TimelineEvent(
                    type="workorder.closed",
                    ts=wo.updated_at,
                    actor=assignee_name,
                    note=f"工单已关闭 · {wo.resolution[:80] if wo.resolution else '关闭'}",
                    target_id=wo.id,
                    target_type="workorder",
                )
            )

    # ── v1.9.7 工单跟进记录（聚合到案件时间线，让 admin/agent/supervisor 共享处理进度）──
    from app.models.work_order_follow_up import WorkOrderFollowUp

    follow_rows = db.execute(
        select(WorkOrderFollowUp, UserAccount.name)
        .join(UserAccount, UserAccount.id == WorkOrderFollowUp.actor_user_id, isouter=True)
        .where(
            WorkOrderFollowUp.case_id == case_id,
            WorkOrderFollowUp.tenant_id == tenant_id,
        )
    ).all()
    for f, actor_name in follow_rows:
        kind_prefix = {
            "note": "工单跟进",
            "resolution_proposed": "工单方案建议",
            "escalation": "工单升级",
        }.get(f.kind, "工单跟进")
        events.append(
            TimelineEvent(
                type="workorder.followup",
                ts=f.occurred_at,
                actor=actor_name,
                note=f"{kind_prefix} · {f.note[:120]}",
                target_id=f.work_order_id,
                target_type="workorder",
            )
        )

    # ── 法务转化 ─────────────────────────────────────────────────
    lc_rows = (
        db.execute(
            select(LegalConversionOrder).where(
                LegalConversionOrder.case_id == case_id,
                LegalConversionOrder.tenant_id == tenant_id,
            )
        )
        .scalars()
        .all()
    )
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

    # ── v1.9.0 物业法务内部处理 actions ────────────────────────
    internal_action_rows = db.execute(
        select(
            LegalInternalAction,
            UserAccount.name,
            InternalLegalLetterTemplate.name,
            PartnerLawFirm.name,
        )
        .join(UserAccount, UserAccount.id == LegalInternalAction.actor_user_id, isouter=True)
        .join(
            InternalLegalLetterTemplate,
            InternalLegalLetterTemplate.id == LegalInternalAction.letter_template_id,
            isouter=True,
        )
        .join(
            PartnerLawFirm,
            PartnerLawFirm.id == LegalInternalAction.partner_law_firm_id,
            isouter=True,
        )
        .where(
            LegalInternalAction.case_id == case_id,
            LegalInternalAction.tenant_id == tenant_id,
        )
    ).all()
    for action, actor_name, tpl_name, firm_name in internal_action_rows:
        event_type = _INTERNAL_ACTION_TYPE_MAP.get(action.action_type, "legal.internal.other")
        # 文案：法务沟通备注；律师函/催告函含模板+律所
        if action.action_type in ("send_lawyer_letter", "send_notice"):
            parts = []
            if tpl_name:
                parts.append(f"模板：{tpl_name}")
            if firm_name:
                parts.append(f"律所：{firm_name}")
            if action.note:
                parts.append(action.note)
            note = " · ".join(parts) if parts else "已出具"
        else:
            note = action.note or ""
        events.append(
            TimelineEvent(
                type=event_type,
                ts=action.occurred_at,
                actor=actor_name,
                note=note,
                target_id=action.legal_order_id,
                target_type="legal_order",
            )
        )

    # ── 法务订单关闭事件（基于 internal_closed_at + close_reason）
    for lc in lc_rows:
        if lc.internal_closed_at and lc.internal_close_reason:
            close_label = {
                "paid": "已缴清",
                "promised": "达成承诺",
                "uncollectible": "无法催收",
                "escalated": "升级到律所",
            }.get(lc.internal_close_reason, lc.internal_close_reason)
            event_type = (
                "legal.internal.escalated"
                if lc.internal_close_reason == "escalated"
                else "legal.internal.closed"
            )
            events.append(
                TimelineEvent(
                    type=event_type,
                    ts=lc.internal_closed_at,
                    actor=None,
                    note=f"法务订单关闭 · {close_label}",
                    target_id=lc.id,
                    target_type="legal_order",
                )
            )

    # ── 法务案件状态 ────────────────────────────────────────────
    legal_cases = (
        db.execute(
            select(LegalCase).where(
                LegalCase.case_id == case_id,
                LegalCase.tenant_id == tenant_id,
            )
        )
        .scalars()
        .all()
    )
    for lc in legal_cases:
        events.append(
            TimelineEvent(
                type="legal.case",
                ts=lc.created_at,
                actor=lc.lawyer_name,
                note=f"法务跟进 · {lc.stage}"
                + (f" ({lc.next_milestone})" if lc.next_milestone else ""),
                target_id=lc.id,
                target_type="legal_case",
            )
        )

    # ── 阶段 / 分配 / 督导动作审计 ────────────────────────────────
    # v0.5.4 — 加 case.reassigned + case.supervisor_*(催回访/催办/介入处理)
    audit_rows = db.execute(
        select(AuditLog, UserAccount.name)
        .join(UserAccount, UserAccount.id == AuditLog.actor_user_id, isouter=True)
        .where(
            AuditLog.target_type == "case",
            AuditLog.target_id == case_id,
            AuditLog.tenant_id == tenant_id,
            AuditLog.action.in_(
                (
                    "case.assigned",
                    "case.stage_changed",
                    "case.escalated",
                    "case.released",
                    "case.reassigned",
                    "case.supervisor_remind_callback",
                    "case.supervisor_urge",
                    "case.supervisor_intervene",
                )
            ),
        )
    ).all()
    for log, actor_name in audit_rows:
        note = log.action
        payload = log.payload or {}
        if log.action == "case.assigned" and "assignee_name" in payload:
            note = f"分配给 {payload['assignee_name']}"
        elif log.action == "case.stage_changed" and "stage" in payload:
            note = f"阶段更新 → {payload['stage']}"
        elif log.action == "case.escalated":
            note = "升级处理"
        elif log.action == "case.released":
            note = "释放至公海"
        elif log.action == "case.reassigned":
            new_name = payload.get("new_assignee_name") or "新催收员"
            note = f"重新分配给 {new_name}"
            if payload.get("note"):
                note += f" · {payload['note']}"
        elif log.action == "case.supervisor_remind_callback":
            note = "督导催回访"
            if payload.get("note"):
                note += f" · {payload['note']}"
        elif log.action == "case.supervisor_urge":
            note = "督导催办"
            if payload.get("note"):
                note += f" · {payload['note']}"
        elif log.action == "case.supervisor_intervene":
            note = "督导介入处理"
            if payload.get("note"):
                note += f" · {payload['note']}"
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
