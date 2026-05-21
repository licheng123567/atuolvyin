"""v1.6.4 — 督导侧升级案件列表 API。

GET /api/v1/supervisor/escalated-cases?page=&page_size=

返回本租户内 stage=escalated 的案件分页列表，督导用于「升级案件处理」页。

v0.6.0 — 介入处理 5 选项扩展:
POST /api/v1/supervisor/escalated/{case_id}/mark-shadow-listening  陪同监听
POST /api/v1/supervisor/escalated/{case_id}/close-as-uncollectible 直接结案/标坏账
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.phone_visibility import (
    display_owner_phone,
    is_provider_contract_active,
    should_reveal_owner_phone,
)
from app.core.security import get_token_payload, require_tenant_roles
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.notification import Notification
from app.models.user import UserAccount
from app.services.audit import log_audit

router = APIRouter()

SUPERVISOR_ROLES = ("supervisor", "admin", "superadmin")


def _require_tenant(payload: dict) -> int:
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )
    return int(tenant_id)


def _load_escalated_case(db: Session, case_id: int, tenant_id: int) -> CollectionCase:
    case = db.get(CollectionCase, case_id)
    if case is None or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不属于本租户"},
        )
    return case


@router.get("/escalated-cases")
async def list_escalated_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )
    tenant_id = int(tenant_id)

    base = (
        select(
            CollectionCase,
            OwnerProfile,
            Project.name.label("project_name"),
            UserAccount.name.label("agent_name"),
        )
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .join(Project, Project.id == CollectionCase.project_id, isouter=True)
        .join(UserAccount, UserAccount.id == CollectionCase.assigned_to, isouter=True)
        .where(
            CollectionCase.tenant_id == tenant_id,
            CollectionCase.stage == "escalated",
        )
    )
    total = db.execute(
        select(func.count(CollectionCase.id)).where(
            CollectionCase.tenant_id == tenant_id,
            CollectionCase.stage == "escalated",
        )
    ).scalar_one()

    rows = db.execute(
        base.order_by(desc(CollectionCase.priority_score), desc(CollectionCase.updated_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    # v1.7.0 — supervisor / admin / superadmin 是物业内部 / 平台角色，统一决策
    role = payload.get("role", "")
    contract_active = is_provider_contract_active(db, tenant_id, payload.get("provider_id"))
    owner_phone_reveal = should_reveal_owner_phone(role=role, provider_id=payload.get("provider_id"), contract_active=contract_active)

    items = []
    for case, owner, project_name, agent_name in rows:
        amount = float(case.amount_owed) if case.amount_owed is not None else 0.0
        # 简易优先级判定：欠费 > 1.5w 或欠 > 12 月 → high
        priority = "high" if amount > 15000 or (case.months_overdue or 0) > 12 else "medium"
        items.append(
            {
                "id": case.id,
                "owner_name": owner.name,
                "building": (owner.building or "") + (owner.room or ""),
                "phone_masked": display_owner_phone(owner.phone_enc, reveal=owner_phone_reveal)
                or "—",
                "amount": amount,
                "months_overdue": case.months_overdue or 0,
                "reason": case.notes or case.arrears_reason or "—",
                "raised_by": agent_name or "—",
                "raised_at": case.updated_at.strftime("%Y-%m-%d %H:%M") if case.updated_at else "—",
                "priority": priority,
                "project_name": project_name or "—",
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# v0.6.0 — 介入处理 ② 标记陪同监听 ──────────────────────────────────
class MarkShadowBody(BaseModel):
    note: str | None = Field(None, max_length=2000)


class EscalatedActionOut(BaseModel):
    case_id: int
    action: str
    note: str | None = None
    notified_user_id: int | None = None


def _notify_agent(
    db: Session,
    *,
    tenant_id: int,
    agent_user_id: int | None,
    case_id: int,
    supervisor_name: str,
    title: str,
    body: str,
) -> None:
    if not agent_user_id:
        return
    db.add(
        Notification(
            tenant_id=tenant_id,
            user_id=agent_user_id,
            event_type="supervisor_action",
            severity="info",
            title=title,
            body=body,
            payload={"case_id": case_id, "supervisor_name": supervisor_name},
        )
    )


@router.post(
    "/escalated/{case_id}/mark-shadow-listening",
    response_model=EscalatedActionOut,
)
def mark_shadow_listening(
    case_id: int,
    body: MarkShadowBody,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> EscalatedActionOut:
    """介入处理 ②:把案件标记为「督导陪同」 — case.shadow_supervisor_id = 当前督导。

    催收员下一次拨打该案件时,实时通话墙会高亮 + 督导自动收通知,可监听或强制接管。
    """
    tenant_id = _require_tenant(payload)
    case = _load_escalated_case(db, case_id, tenant_id)
    user_id = int(payload.get("user_id") or 0)
    user = db.get(UserAccount, user_id)
    actor_name = user.name if user else "督导"

    case.shadow_supervisor_id = user_id

    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=str(payload.get("role") or ""),
        tenant_id=tenant_id,
        action="case.supervisor_shadow_listening",
        target_type="case",
        target_id=case.id,
        payload={"note": body.note, "supervisor_id": user_id},
    )

    _notify_agent(
        db,
        tenant_id=tenant_id,
        agent_user_id=case.assigned_to,
        case_id=case.id,
        supervisor_name=actor_name,
        title=f"督导陪同监听 · 案件 #{case_id}",
        body=(
            f"督导 {actor_name} 已标记本案件为陪同监听 — 下次拨打时督导会同步收到通知"
            + (f"\n备注:{body.note}" if body.note else "")
        ),
    )

    db.commit()
    return EscalatedActionOut(
        case_id=case.id,
        action="mark_shadow_listening",
        note=body.note,
        notified_user_id=case.assigned_to,
    )


# v0.6.0 — 介入处理 ③ 直接结案 / 标坏账 ──────────────────────────────
class CloseUncollectibleBody(BaseModel):
    """必填原因 — 后端会校验非空并写 close_reason + stage='pending_close'。"""

    reason: str = Field(..., min_length=1, max_length=2000)


@router.post(
    "/escalated/{case_id}/close-as-uncollectible",
    response_model=EscalatedActionOut,
)
def close_as_uncollectible(
    case_id: int,
    body: CloseUncollectibleBody,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> EscalatedActionOut:
    """介入处理 ③:申请直接结案 / 标坏账。

    动作:
      - case.stage → 'pending_close'(等物业管理员二审)
      - case.close_reason = 原因
      - 写 audit log + 通知原催收员 + 通知所有 admin
    """
    tenant_id = _require_tenant(payload)
    case = _load_escalated_case(db, case_id, tenant_id)
    user_id = int(payload.get("user_id") or 0)
    user = db.get(UserAccount, user_id)
    actor_name = user.name if user else "督导"

    if case.stage in ("pending_close", "closed", "uncollectible"):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_ALREADY_CLOSING",
                "message": f"案件已在结案流程(stage={case.stage})",
            },
        )

    old_stage = case.stage
    case.stage = "pending_close"
    case.close_reason = body.reason

    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=str(payload.get("role") or ""),
        tenant_id=tenant_id,
        action="case.supervisor_close_as_uncollectible",
        target_type="case",
        target_id=case.id,
        payload={"reason": body.reason, "old_stage": old_stage},
    )

    _notify_agent(
        db,
        tenant_id=tenant_id,
        agent_user_id=case.assigned_to,
        case_id=case.id,
        supervisor_name=actor_name,
        title=f"案件待结案审批 · #{case_id}",
        body=f"督导 {actor_name} 申请结案 / 标坏账\n原因:{body.reason}",
    )

    db.commit()
    return EscalatedActionOut(
        case_id=case.id,
        action="close_as_uncollectible",
        note=body.reason,
        notified_user_id=case.assigned_to,
    )
