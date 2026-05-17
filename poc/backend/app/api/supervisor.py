from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_tenant_roles
from app.models.case import CollectionCase, OwnerProfile
from app.models.user import UserAccount
from app.schemas.case import CaseWithOwnerResponse
from app.schemas.common import PaginatedResponse

from .admin_cases import _case_row_to_response, _require_tenant

router = APIRouter()

SUPERVISOR_ROLES = ("supervisor",)


@router.get("/cases", response_model=PaginatedResponse[CaseWithOwnerResponse])
async def list_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    stage: str | None = Query(None),
    pool_type: str | None = Query(None),
    assigned_to: int | None = Query(None),
    keyword: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CaseWithOwnerResponse]:
    tenant_id = _require_tenant(payload)
    # Supervisor sees all tenant cases; group-level scoping deferred to Sprint 3

    stmt = (
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(CollectionCase.tenant_id == tenant_id)
    )
    if stage:
        stmt = stmt.where(CollectionCase.stage == stage)
    if pool_type:
        stmt = stmt.where(CollectionCase.pool_type == pool_type)
    if assigned_to:
        stmt = stmt.where(CollectionCase.assigned_to == assigned_to)
    if keyword:
        stmt = stmt.where(OwnerProfile.name.ilike(f"%{keyword}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    rows = db.execute(
        stmt.order_by(CollectionCase.priority_score.desc(), CollectionCase.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    # v1.7.0 — supervisor 是物业内部角色，列表内电话明文
    from app.core.phone_visibility import should_reveal_owner_phone

    owner_phone_reveal = should_reveal_owner_phone(role=payload.get("role", ""), provider_id=payload.get("provider_id"))

    return PaginatedResponse(
        items=[
            _case_row_to_response(case, owner, owner_phone_reveal=owner_phone_reveal)
            for case, owner in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
