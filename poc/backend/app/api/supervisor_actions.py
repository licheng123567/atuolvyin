"""v0.5.4 — 督导对案件的快速操作:催回访 / 催办 / 介入处理 / 重新分配。

每个动作:
  1. 写 AuditLog (action=case.supervisor_*),由 case_timeline.py 聚合到案件时间线
  2. 给原催收员 (reassign 时为新催收员) 发 Notification (event_type=supervisor_action)
  3. 重新分配额外更新 CollectionCase.assigned_to

GET 端点不在此处;查询走通用的 case detail。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_tenant_roles
from app.models.case import CollectionCase
from app.models.notification import Notification
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.services.audit import log_audit

router = APIRouter()

SUPERVISOR_ROLES = ("supervisor", "admin", "superadmin")


def _require_tenant(payload: dict) -> int:
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    return int(tenant_id)


def _load_case(db: Session, case_id: int, tenant_id: int) -> CollectionCase:
    case = db.get(CollectionCase, case_id)
    if case is None or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不属于本租户"},
        )
    return case


def _notify_agent(
    db: Session,
    *,
    tenant_id: int,
    agent_user_id: int | None,
    case_id: int,
    supervisor_name: str,
    action_label: str,
    note: str | None,
) -> None:
    """给催收员发站内信通知(system 渠道直接写 notification 表)。"""
    if not agent_user_id:
        return
    body = f"督导 {supervisor_name} 对案件 #{case_id} 执行了「{action_label}」"
    if note:
        body += f"\n备注:{note}"
    notif = Notification(
        tenant_id=tenant_id,
        user_id=agent_user_id,
        event_type="supervisor_action",
        severity="info",
        title=f"督导{action_label} · 案件 #{case_id}",
        body=body,
        payload={
            "case_id": case_id,
            "action_label": action_label,
            "note": note,
        },
    )
    db.add(notif)


class CaseActionBody(BaseModel):
    """催回访 / 催办 / 介入处理 用同一个 body(note 选填,介入处理建议填)。"""

    note: str | None = Field(None, max_length=2000)


class CaseInterveneBody(BaseModel):
    """介入处理:note 必填(说明介入原因)。"""

    note: str = Field(..., min_length=1, max_length=2000)


class CaseReassignBody(BaseModel):
    target_user_id: int = Field(..., gt=0, description="目标催收员 user_id")
    note: str | None = Field(None, max_length=2000)


class CaseActionOut(BaseModel):
    case_id: int
    action: str  # remind_callback / urge / intervene / reassign
    note: str | None = None
    notified_user_id: int | None = None
    new_assigned_to: int | None = None  # 仅 reassign 时设


def _do_action(
    db: Session,
    *,
    case: CollectionCase,
    actor_user_id: int,
    actor_role: str,
    actor_name: str,
    tenant_id: int,
    audit_action: str,
    action_key: str,
    action_label: str,
    note: str | None,
) -> CaseActionOut:
    """催回访 / 催办 / 介入处理 共享路径:写 audit + notify。"""
    log_audit(
        db,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        tenant_id=tenant_id,
        action=audit_action,
        target_type="case",
        target_id=case.id,
        payload={"note": note},
    )
    _notify_agent(
        db,
        tenant_id=tenant_id,
        agent_user_id=case.assigned_to,
        case_id=case.id,
        supervisor_name=actor_name,
        action_label=action_label,
        note=note,
    )
    db.commit()
    return CaseActionOut(
        case_id=case.id,
        action=action_key,
        note=note,
        notified_user_id=case.assigned_to,
    )


@router.post("/cases/{case_id}/remind-callback", response_model=CaseActionOut)
def remind_callback(
    case_id: int,
    body: CaseActionBody,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseActionOut:
    """督导提醒催收员回访该案件 — 推一条通知 + 写 timeline。"""
    tenant_id = _require_tenant(payload)
    case = _load_case(db, case_id, tenant_id)
    user_id = int(payload.get("user_id") or 0)
    user = db.get(UserAccount, user_id)
    return _do_action(
        db,
        case=case,
        actor_user_id=user_id,
        actor_role=str(payload.get("role") or ""),
        actor_name=user.name if user else "督导",
        tenant_id=tenant_id,
        audit_action="case.supervisor_remind_callback",
        action_key="remind_callback",
        action_label="催回访",
        note=body.note,
    )


@router.post("/cases/{case_id}/urge", response_model=CaseActionOut)
def urge(
    case_id: int,
    body: CaseActionBody,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseActionOut:
    """督导对停滞案件发催办,提醒催收员尽快推进。"""
    tenant_id = _require_tenant(payload)
    case = _load_case(db, case_id, tenant_id)
    user_id = int(payload.get("user_id") or 0)
    user = db.get(UserAccount, user_id)
    return _do_action(
        db,
        case=case,
        actor_user_id=user_id,
        actor_role=str(payload.get("role") or ""),
        actor_name=user.name if user else "督导",
        tenant_id=tenant_id,
        audit_action="case.supervisor_urge",
        action_key="urge",
        action_label="催办",
        note=body.note,
    )


@router.post("/cases/{case_id}/intervene", response_model=CaseActionOut)
def intervene(
    case_id: int,
    body: CaseInterveneBody,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseActionOut:
    """督导接管/介入处理 — note 必填(说明介入原因)。"""
    tenant_id = _require_tenant(payload)
    case = _load_case(db, case_id, tenant_id)
    user_id = int(payload.get("user_id") or 0)
    user = db.get(UserAccount, user_id)
    return _do_action(
        db,
        case=case,
        actor_user_id=user_id,
        actor_role=str(payload.get("role") or ""),
        actor_name=user.name if user else "督导",
        tenant_id=tenant_id,
        audit_action="case.supervisor_intervene",
        action_key="intervene",
        action_label="介入处理",
        note=body.note,
    )


@router.post("/cases/{case_id}/reassign", response_model=CaseActionOut)
def reassign(
    case_id: int,
    body: CaseReassignBody,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseActionOut:
    """督导重新分配案件给另一个催收员 — 更新 assigned_to + 通知双方。"""
    tenant_id = _require_tenant(payload)
    case = _load_case(db, case_id, tenant_id)
    user_id = int(payload.get("user_id") or 0)
    user = db.get(UserAccount, user_id)
    actor_name = user.name if user else "督导"

    # 验证目标用户是本租户内的催收员
    target_membership = (
        db.query(UserTenantMembership)
        .filter(
            UserTenantMembership.user_id == body.target_user_id,
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.role == "agent",
            UserTenantMembership.is_active.is_(True),
        )
        .one_or_none()
    )
    if target_membership is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_INVALID_TARGET",
                "message": "目标用户不存在或不是本租户催收员",
            },
        )

    old_assigned_to = case.assigned_to
    target_user = db.get(UserAccount, body.target_user_id)
    target_name = target_user.name if target_user else "新催收员"

    case.assigned_to = body.target_user_id
    # 流转到私海(若原是公海)
    case.pool_type = "private"

    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=str(payload.get("role") or ""),
        tenant_id=tenant_id,
        action="case.reassigned",
        target_type="case",
        target_id=case.id,
        payload={
            "old_assigned_to": old_assigned_to,
            "new_assigned_to": body.target_user_id,
            "new_assignee_name": target_name,
            "note": body.note,
        },
    )
    # 通知新催收员(被分配)
    _notify_agent(
        db,
        tenant_id=tenant_id,
        agent_user_id=body.target_user_id,
        case_id=case.id,
        supervisor_name=actor_name,
        action_label="重新分配给你",
        note=body.note,
    )
    # 若有原催收员也通知一下(被替换)
    if old_assigned_to and old_assigned_to != body.target_user_id:
        _notify_agent(
            db,
            tenant_id=tenant_id,
            agent_user_id=old_assigned_to,
            case_id=case.id,
            supervisor_name=actor_name,
            action_label=f"案件已转出给 {target_name}",
            note=body.note,
        )

    db.commit()
    return CaseActionOut(
        case_id=case.id,
        action="reassign",
        note=body.note,
        notified_user_id=body.target_user_id,
        new_assigned_to=body.target_user_id,
    )
