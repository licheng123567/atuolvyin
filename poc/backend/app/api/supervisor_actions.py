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
from app.core.security import get_token_payload, require_roles, require_tenant_roles  # noqa: F401
from app.models.case import CollectionCase
from app.models.notification import Notification
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.services.audit import log_audit

# v0.7.0 — 引入 supervisor_scope,允许服务商督导对自己接的项目案件执行动作
from ._supervisor_scope import (
    SupervisorScope,
    supervisor_case_filter,
    supervisor_scope,
)

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
    """v0.5.4 老签名 — 仅 tenant_id 校验。新代码请用 _load_case_scoped。"""
    case = db.get(CollectionCase, case_id)
    if case is None or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不属于本租户"},
        )
    return case


def _load_case_scoped(db: Session, case_id: int, scope: SupervisorScope) -> CollectionCase:
    """v0.7.0 — 用 supervisor_case_filter 校验:
    物业督导看本租户内 + 非服务商接案;服务商督导看本服务商接的项目案件。
    """
    from sqlalchemy import select

    case = db.execute(
        select(CollectionCase)
        .where(CollectionCase.id == case_id)
        .where(supervisor_case_filter(scope))
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ERR_NOT_FOUND",
                "message": "案件不存在或不在本督导可见范围",
            },
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
    _user: Annotated[UserAccount, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> CaseActionOut:
    """督导提醒催收员回访该案件 — 推一条通知 + 写 timeline。
    v0.7.0 — scope 校验,服务商督导只能对自己接的项目案件做催回访。
    """
    tenant_id = scope.tenant_id
    case = _load_case_scoped(db, case_id, scope)
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
    _user: Annotated[UserAccount, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> CaseActionOut:
    """督导对停滞案件发催办,提醒催收员尽快推进。v0.7.0 — scope 守卫。"""
    tenant_id = scope.tenant_id
    case = _load_case_scoped(db, case_id, scope)
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
    _user: Annotated[UserAccount, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> CaseActionOut:
    """督导接管/介入处理 — note 必填(说明介入原因)。v0.7.0 — scope 守卫。"""
    tenant_id = scope.tenant_id
    case = _load_case_scoped(db, case_id, scope)
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
    _user: Annotated[UserAccount, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> CaseActionOut:
    """督导重新分配案件给另一个催收员 — 更新 assigned_to + 通知双方。v0.7.0 — scope 守卫。"""
    tenant_id = scope.tenant_id
    case = _load_case_scoped(db, case_id, scope)
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


# v0.6.0 — 督导直接「移交法务」(无催收员申请时使用,绕过 LegalConversionRequest 审批环节)
class TransferLegalBody(BaseModel):
    """督导直接移交法务时必填原因 — 写入 audit log + case timeline。"""

    reason: str = Field(..., min_length=1, max_length=2000)


@router.post("/cases/{case_id}/transfer-legal", response_model=CaseActionOut)
def transfer_legal_direct(
    case_id: int,
    body: TransferLegalBody,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> CaseActionOut:
    """督导跳过申请-审批流,直接把案件移交法务。

    适用场景:本案件无 LegalConversionRequest(pending/pending_admin)挂起。
    若已有 pending 申请:返回 409,提示用「审批转法务」端点处理那个申请。

    动作:
      - case.stage → 'legal'
      - 写 audit (case.supervisor_transfer_legal_direct,payload={reason})
      - 给原催收员发通知「已直接转法务」

    v0.7.0 — scope 守卫:服务商督导可直接移交本服务商接的项目案件;
              不能操作非本服务商接案。
    """
    from sqlalchemy import select

    from app.models.legal_conversion import LegalConversionRequest

    tenant_id = scope.tenant_id
    case = _load_case_scoped(db, case_id, scope)
    user_id = int(payload.get("user_id") or 0)
    user = db.get(UserAccount, user_id)

    # 不允许在已有 pending 申请的情况下越权直接转 — 防双轨
    existing_req = db.execute(
        select(LegalConversionRequest)
        .where(
            LegalConversionRequest.case_id == case_id,
            LegalConversionRequest.status.in_(("pending", "pending_admin")),
        )
        .limit(1)
    ).scalar_one_or_none()
    if existing_req is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_PENDING_REQUEST_EXISTS",
                "message": (
                    f"本案件已有等审批的法务转化申请 #{existing_req.id}, "
                    "请去「审批转法务」处理,不要直接越权移交"
                ),
            },
        )

    if case.stage == "legal":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_ALREADY_LEGAL", "message": "案件已在法务阶段"},
        )

    old_stage = case.stage
    case.stage = "legal"

    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=str(payload.get("role") or ""),
        tenant_id=tenant_id,
        action="case.supervisor_transfer_legal_direct",
        target_type="case",
        target_id=case.id,
        payload={"reason": body.reason, "old_stage": old_stage},
    )

    _notify_agent(
        db,
        tenant_id=tenant_id,
        agent_user_id=case.assigned_to,
        case_id=case.id,
        supervisor_name=user.name if user else "督导",
        action_label="案件已直接转法务",
        note=body.reason,
    )

    db.commit()
    return CaseActionOut(
        case_id=case.id,
        action="transfer_legal_direct",
        note=body.reason,
        notified_user_id=case.assigned_to,
    )


# v0.6.0 — 案件超期预警:释放回公海(被业主拉黑等情况)
class ReleaseToPoolBody(BaseModel):
    note: str | None = Field(None, max_length=2000)


@router.post("/cases/{case_id}/release-to-pool", response_model=CaseActionOut)
def release_to_pool(
    case_id: int,
    body: ReleaseToPoolBody,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> CaseActionOut:
    """督导把案件从私海释放回公海 — case.assigned_to = NULL + pool_type='public'。

    适用场景:业主连续多通无接 / 拉黑 / 催收员长期无进展,释放让其他催收员尝试。
    v0.7.0 — scope 守卫。
    """
    tenant_id = scope.tenant_id
    case = _load_case_scoped(db, case_id, scope)
    user_id = int(payload.get("user_id") or 0)
    user = db.get(UserAccount, user_id)

    if case.pool_type == "public" and case.assigned_to is None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_ALREADY_PUBLIC", "message": "案件已在公海"},
        )

    old_agent = case.assigned_to
    case.assigned_to = None
    case.pool_type = "public"

    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=str(payload.get("role") or ""),
        tenant_id=tenant_id,
        action="case.supervisor_release_to_pool",
        target_type="case",
        target_id=case.id,
        payload={"old_assigned_to": old_agent, "note": body.note},
    )
    if old_agent:
        _notify_agent(
            db,
            tenant_id=tenant_id,
            agent_user_id=old_agent,
            case_id=case.id,
            supervisor_name=user.name if user else "督导",
            action_label="案件已释放回公海",
            note=body.note,
        )

    db.commit()
    return CaseActionOut(
        case_id=case.id,
        action="release_to_pool",
        note=body.note,
        notified_user_id=old_agent,
    )


# v0.9.0 — 批量分配 / 重派
class CaseBatchAssignBody(BaseModel):
    case_ids: list[int] = Field(..., min_length=1, max_length=200)
    target_user_id: int = Field(..., gt=0, description="目标催收员 user_id")
    note: str | None = Field(None, max_length=2000)


class BatchAssignFailureItem(BaseModel):
    case_id: int
    code: str
    message: str


class BatchAssignResult(BaseModel):
    success_count: int
    failed: list[BatchAssignFailureItem]


@router.post("/cases/batch-assign", response_model=BatchAssignResult)
def batch_assign(
    body: CaseBatchAssignBody,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> BatchAssignResult:
    """督导批量分配 / 重派多个案件给同一催收员。

    复用单条 reassign 的核心逻辑(targets 校验 + assigned_to 切换 + 审计 + 通知),
    但每条 case 单独 try/catch — 一条失败不影响其他。返回成功数 + 失败明细。
    """
    tenant_id = scope.tenant_id
    user_id = int(payload.get("user_id") or 0)
    user = db.get(UserAccount, user_id)
    actor_name = user.name if user else "督导"
    actor_role = str(payload.get("role") or "")

    # 1) 一次性校验目标催收员是本租户的有效 agent
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
                "message": "目标用户不存在或不是本租户有效催收员",
            },
        )
    target_user = db.get(UserAccount, body.target_user_id)
    target_name = target_user.name if target_user else "新催收员"

    # 2) 逐 case_id 处理,记录成功 / 失败
    success_count = 0
    failed: list[BatchAssignFailureItem] = []
    notified_old_agents: set[int] = set()

    for cid in body.case_ids:
        try:
            case = _load_case_scoped(db, cid, scope)
        except HTTPException as exc:
            failed.append(
                BatchAssignFailureItem(
                    case_id=cid,
                    code=str(
                        exc.detail.get("code") if isinstance(exc.detail, dict) else "ERR_NOT_FOUND"
                    ),
                    message=str(
                        exc.detail.get("message")
                        if isinstance(exc.detail, dict)
                        else "案件不可访问"
                    ),
                )
            )
            continue

        # 跳过已分配给目标的(幂等)
        if case.assigned_to == body.target_user_id:
            failed.append(
                BatchAssignFailureItem(
                    case_id=cid,
                    code="ERR_ALREADY_ASSIGNED",
                    message="已分配给该催收员,跳过",
                )
            )
            continue

        old_assigned_to = case.assigned_to
        case.assigned_to = body.target_user_id
        case.pool_type = "private"

        log_audit(
            db,
            actor_user_id=user_id,
            actor_role=actor_role,
            tenant_id=tenant_id,
            action="case.reassigned",
            target_type="case",
            target_id=case.id,
            payload={
                "old_assigned_to": old_assigned_to,
                "new_assigned_to": body.target_user_id,
                "new_assignee_name": target_name,
                "note": body.note,
                "batch": True,
            },
        )
        # 给新催收员每条通知(让其看到具体案件 id)
        _notify_agent(
            db,
            tenant_id=tenant_id,
            agent_user_id=body.target_user_id,
            case_id=case.id,
            supervisor_name=actor_name,
            action_label="重新分配给你",
            note=body.note,
        )
        # 原催收员只通知一次(批量时避免 spam) — 这里简化为每条都通知一次,
        # 但若同一 old_assigned_to 多个案件,只发首条
        if (
            old_assigned_to
            and old_assigned_to != body.target_user_id
            and old_assigned_to not in notified_old_agents
        ):
            notified_old_agents.add(old_assigned_to)
            _notify_agent(
                db,
                tenant_id=tenant_id,
                agent_user_id=old_assigned_to,
                case_id=case.id,
                supervisor_name=actor_name,
                action_label=f"批量分配 — 你的部分案件已转给 {target_name}",
                note=body.note,
            )
        success_count += 1

    db.commit()
    return BatchAssignResult(success_count=success_count, failed=failed)
