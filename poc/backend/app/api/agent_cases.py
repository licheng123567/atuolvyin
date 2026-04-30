from __future__ import annotations

from typing import Annotated, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.case import CollectionCase, OwnerProfile
from app.models.user import UserAccount
from app.schemas.case import CaseResponse, CaseWithOwnerResponse
from app.schemas.common import PaginatedResponse

from .admin_cases import _case_row_to_response, _require_tenant

router = APIRouter()

AGENT_ROLES = ("agent_internal", "agent_external")


@router.get("/cases", response_model=PaginatedResponse[CaseWithOwnerResponse])
async def list_my_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    pool_type: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CaseWithOwnerResponse]:
    tenant_id = _require_tenant(payload)

    # Agent sees: their own private cases OR unassigned public pool cases
    stmt = (
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(
            CollectionCase.tenant_id == tenant_id,
            sa.or_(
                CollectionCase.assigned_to == user.id,
                sa.and_(
                    CollectionCase.pool_type == "public",
                    CollectionCase.assigned_to.is_(None),
                ),
            ),
        )
    )
    if pool_type:
        stmt = stmt.where(CollectionCase.pool_type == pool_type)
    if stage:
        stmt = stmt.where(CollectionCase.stage == stage)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    rows = db.execute(
        stmt.order_by(
            CollectionCase.assigned_to.desc().nulls_last(),
            CollectionCase.priority_score.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[_case_row_to_response(case, owner) for case, owner in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/cases/{case_id}/claim", response_model=CaseResponse)
async def claim_case(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseResponse:
    tenant_id = _require_tenant(payload)
    case = db.get(CollectionCase, case_id)
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    if case.pool_type != "public" or case.assigned_to is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_ALREADY_CLAIMED", "message": "案件已被认领或不在公池"},
        )
    case.pool_type = "private"
    case.assigned_to = user.id
    db.commit()
    db.refresh(case)
    return case
