"""v1.0.0 — 服务商审计日志(对齐物业 admin/audit-logs)。

诱因:用户反馈服务商应该有自己的审计日志(可看自家成员操作 + 与本服务商相关案件的操作)。

查询逻辑:
  - 主条件:AuditLog.provider_id == self_provider(新写入的服务商动作)
  - 备用条件:AuditLog.target_type='case' AND target_id IN (本服务商接的案件 ids)
    (兜底旧动作 — 老代码 log_audit 没传 provider_id,但 target_id 是 case)
  - OR 二者合并展示给服务商管理员
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_provider_roles
from app.models.audit import AuditLog
from app.models.case import CollectionCase, Project
from app.models.tenant import UserTenantMembership
from app.schemas.common import PaginatedResponse

router = APIRouter()

PROVIDER_ADMIN_ROLES = ("admin",)


class AuditLogOut(BaseModel):
    id: int
    actor_user_id: int | None
    actor_role: str | None
    tenant_id: int | None
    provider_id: int | None
    action: str
    target_type: str | None
    target_id: int | None
    payload: dict[str, Any] | None
    created_at: datetime


def _resolve_provider_id(payload: dict, db: Session) -> int:
    user_id = int(payload.get("user_id") or 0)
    if not user_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Invalid token"},
        )
    membership = (
        db.execute(
            select(UserTenantMembership)
            .where(UserTenantMembership.user_id == user_id)
            .where(UserTenantMembership.provider_id.isnot(None))
        )
        .scalars()
        .first()
    )
    if membership is None or membership.provider_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NO_PROVIDER", "message": "当前账号未绑定任何服务商"},
        )
    return int(membership.provider_id)


@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogOut])
async def list_provider_audit_logs(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_provider_roles(*PROVIDER_ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    action: str | None = Query(None, description="按 action 前缀过滤,如 case."),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
) -> PaginatedResponse[AuditLogOut]:
    provider_id = _resolve_provider_id(payload, db)

    # 本服务商接的案件 id 子查询(target_type='case' 兜底)
    case_ids_subq = (
        select(CollectionCase.id)
        .join(Project, Project.id == CollectionCase.project_id)
        .where(Project.provider_id == provider_id)
        .subquery()
    )

    # 主 + 兜底:provider_id == self_provider 或 (target_type='case' AND target_id IN cases)
    scope_filter = or_(
        AuditLog.provider_id == provider_id,
        (AuditLog.target_type == "case")
        & (AuditLog.target_id.in_(select(case_ids_subq.c.id))),
    )

    stmt = select(AuditLog).where(scope_filter)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    return PaginatedResponse(
        items=[
            AuditLogOut(
                id=r.id,
                actor_user_id=r.actor_user_id,
                actor_role=r.actor_role,
                tenant_id=r.tenant_id,
                provider_id=getattr(r, "provider_id", None),
                action=r.action,
                target_type=r.target_type,
                target_id=r.target_id,
                payload=r.payload,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
