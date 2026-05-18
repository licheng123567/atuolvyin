"""Sprint 15.2 — 通话干预服务 (PRD §13 / §11.2)。

两个触发路径：
  1. 风控检测器检测到 L3 事件 + TenantSettings.l3_hangup_enabled=True → 自动触发
  2. 督导从实时通话墙手动点「强制结束」(Sprint 15.3 SUPERVISOR_TAKEOVER 共用此通道)

WS 推送：
  - 通道 /ws/calls/{call_id} 房间内广播 `{"type":"call.force_hangup", "reason":"..."}`
  - agent App 端收到后弹紧急对话框 + 强振动 + 提示坐席立即挂断
  - 同步推 supervisor 房间 `{"type":"call.intervention","call_id":X,"action":"force_hangup",...}`

Audit：每次干预写一条 audit_log，留法律存证。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.call import CallRecord
from app.models.settings import TenantSettings
from app.services.audit import log_audit

logger = logging.getLogger(__name__)


def is_l3_hangup_enabled(db: Session, tenant_id: int) -> bool:
    """读取 TenantSettings.l3_hangup_enabled；默认 False。"""
    settings = db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    ).scalar_one_or_none()
    return bool(settings and settings.l3_hangup_enabled)


def _resolve_call_provider_id(db: Session, call_id: int) -> int | None:
    """通话归属服务商 id —— 给 SupervisorManager.broadcast 的 scope 过滤用。"""
    from app.api._supervisor_scope import resolve_call_provider_id

    case_id = db.execute(
        select(CallRecord.case_id).where(CallRecord.id == call_id)
    ).scalar_one_or_none()
    return resolve_call_provider_id(db, case_id)


async def dispatch_force_hangup(
    db: Session,
    *,
    call_id: int,
    tenant_id: int,
    reason: str,
    triggered_by: str,  # "risk.l3_auto" | "supervisor.manual"
    supervisor_user_id: int | None = None,
) -> dict:
    """触发强制挂断：WS 推 agent + supervisor 房间 + audit log。
    返回事件 payload 给调用方做 ack。
    """
    # WS push 给 agent 房间（call-level）
    from app.api.ws_calls import _sessions
    from app.risk.supervisor_manager import get_supervisor_manager
    from app.ws.connection_manager import get_connection_manager

    # 解析通话归属服务商（用于 supervisor 房间 scope 过滤）
    call_provider_id = _resolve_call_provider_id(db, call_id)

    payload_agent = {
        "type": "call.force_hangup",
        "call_id": call_id,
        "reason": reason,
        "triggered_by": triggered_by,
    }
    try:
        await get_connection_manager().broadcast(call_id, payload_agent)
    except Exception as exc:
        logger.warning("force_hangup agent broadcast failed call=%s: %s", call_id, exc)

    # 同步给 supervisor 房间
    payload_sup = {
        "type": "call.intervention",
        "call_id": call_id,
        "action": "force_hangup",
        "reason": reason,
        "triggered_by": triggered_by,
        "supervisor_user_id": supervisor_user_id,
        "ts": datetime.now(UTC).isoformat(),
    }
    try:
        await get_supervisor_manager().broadcast(
            tenant_id, payload_sup, call_provider_id=call_provider_id
        )
    except Exception as exc:
        logger.warning("force_hangup supervisor broadcast failed tenant=%s: %s", tenant_id, exc)

    # Audit log
    log_audit(
        db,
        actor_user_id=supervisor_user_id,  # None for auto-triggered
        actor_role="system" if triggered_by == "risk.l3_auto" else "supervisor",
        tenant_id=tenant_id,
        action="call.force_hangup",
        target_type="call_record",
        target_id=call_id,
        payload={"reason": reason, "triggered_by": triggered_by},
    )
    db.commit()

    # 标记 CallSession 也清理（in-process）
    sess = _sessions.get(call_id)
    if sess is not None:
        try:
            await sess.stop()
        except Exception as exc:
            logger.warning("session.stop failed call=%s: %s", call_id, exc)
        _sessions.pop(call_id, None)

    return payload_agent


async def maybe_auto_hangup_for_l3(db: Session, *, call_id: int, risk_event: dict) -> bool:
    """风控管线检测到 L3 时调用。返回是否实际触发了挂断。"""
    if risk_event.get("level") != "L3":
        return False
    call = db.get(CallRecord, call_id)
    if call is None:
        return False
    if not is_l3_hangup_enabled(db, call.tenant_id):
        logger.info("L3 detected on call=%s but l3_hangup_enabled=False; skip", call_id)
        return False
    reason = (
        f"L3 风控触发：{risk_event.get('category', 'unknown')}（"
        f"匹配「{(risk_event.get('matched_keywords') or ['?'])[0]}」）"
    )
    await dispatch_force_hangup(
        db,
        call_id=call_id,
        tenant_id=call.tenant_id,
        reason=reason,
        triggered_by="risk.l3_auto",
    )
    return True


# ── Sprint 15.3 — 督导一键介入 (SUPERVISOR_TAKEOVER, PRD §11.2) ──


async def dispatch_takeover_request(
    db: Session,
    *,
    call_id: int,
    tenant_id: int,
    supervisor_user_id: int,
    supervisor_name: str,
    reason: str,
) -> dict:
    """督导发起强制转接请求：WS 推 agent + audit。等 agent 决策后调
    dispatch_takeover_response 通知 supervisor。"""
    from app.risk.supervisor_manager import get_supervisor_manager
    from app.ws.connection_manager import get_connection_manager

    # 解析通话归属服务商（用于 supervisor 房间 scope 过滤）
    call_provider_id = _resolve_call_provider_id(db, call_id)

    payload = {
        "type": "supervisor.takeover_request",
        "call_id": call_id,
        "supervisor_user_id": supervisor_user_id,
        "supervisor_name": supervisor_name,
        "reason": reason,
        "ts": datetime.now(UTC).isoformat(),
    }
    try:
        await get_connection_manager().broadcast(call_id, payload)
    except Exception as exc:
        logger.warning("takeover request broadcast (agent) failed call=%s: %s", call_id, exc)

    # Supervisor wall 同时收到一个 pending 状态
    sup_payload = {
        "type": "call.intervention",
        "call_id": call_id,
        "action": "takeover_requested",
        "supervisor_user_id": supervisor_user_id,
        "supervisor_name": supervisor_name,
        "reason": reason,
        "ts": payload["ts"],
    }
    try:
        await get_supervisor_manager().broadcast(
            tenant_id, sup_payload, call_provider_id=call_provider_id
        )
    except Exception as exc:
        logger.warning("takeover request broadcast (sup) failed tenant=%s: %s", tenant_id, exc)

    log_audit(
        db,
        actor_user_id=supervisor_user_id,
        actor_role="supervisor",
        tenant_id=tenant_id,
        action="call.takeover_requested",
        target_type="call_record",
        target_id=call_id,
        payload={"reason": reason},
    )
    db.commit()
    return payload


async def dispatch_takeover_response(
    db: Session,
    *,
    call_id: int,
    tenant_id: int,
    agent_user_id: int,
    accepted: bool,
    note: str | None = None,
) -> dict:
    """agent 响应督导转接：accepted=True/False。"""
    from app.risk.supervisor_manager import get_supervisor_manager
    from app.ws.connection_manager import get_connection_manager

    # 解析通话归属服务商（用于 supervisor 房间 scope 过滤）
    call_provider_id = _resolve_call_provider_id(db, call_id)

    action = "takeover_accepted" if accepted else "takeover_rejected"
    payload = {
        "type": "call.intervention",
        "call_id": call_id,
        "action": action,
        "agent_user_id": agent_user_id,
        "note": note,
        "ts": datetime.now(UTC).isoformat(),
    }
    # 给 supervisor wall 推
    try:
        await get_supervisor_manager().broadcast(
            tenant_id, payload, call_provider_id=call_provider_id
        )
    except Exception as exc:
        logger.warning("takeover response broadcast failed: %s", exc)

    # 同步给 agent 房间一个 ack（清掉 modal）
    ack = {"type": "supervisor.takeover_ack", "call_id": call_id, "accepted": accepted}
    try:
        await get_connection_manager().broadcast(call_id, ack)
    except Exception as exc:
        logger.warning("takeover ack to agent room failed: %s", exc)

    log_audit(
        db,
        actor_user_id=agent_user_id,
        actor_role="agent",
        tenant_id=tenant_id,
        action=f"call.{action}",
        target_type="call_record",
        target_id=call_id,
        payload={"note": note},
    )
    db.commit()
    return payload
