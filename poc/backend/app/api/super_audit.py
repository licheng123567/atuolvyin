"""Sprint 15 — platform_super audit log listing.

GET /api/v1/super/audit-logs   — paginated list with filters
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_roles
from app.models.audit import AuditLog
from app.models.user import UserAccount
from app.schemas.audit import AuditLogOut
from app.schemas.common import PaginatedResponse

router = APIRouter()

SUPER_ROLES = ("platform_super", "platform_superadmin")


@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogOut])
async def list_audit_logs(
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    action: str | None = Query(None, max_length=100),
    actor_user_id: int | None = Query(None, ge=1),
    tenant_id: int | None = Query(None, ge=1),
    target_type: str | None = Query(None, max_length=50),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[AuditLogOut]:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if tenant_id:
        stmt = stmt.where(AuditLog.tenant_id == tenant_id)
    if target_type:
        stmt = stmt.where(AuditLog.target_type == target_type)
    if since:
        stmt = stmt.where(AuditLog.created_at >= since)
    if until:
        stmt = stmt.where(AuditLog.created_at <= until)

    total: int = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()

    rows = (
        db.execute(
            stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedResponse(
        items=[AuditLogOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
