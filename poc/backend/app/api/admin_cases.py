from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import (
    get_token_payload,
    mask_phone,
    require_roles,
)
from app.models.case import CollectionCase, OwnerProfile
from app.models.user import UserAccount
from app.schemas.case import (
    CaseImportRequest,
    CaseImportResponse,
    CaseWithOwnerResponse,
    OwnerInfo,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()

ADMIN_ROLES = ("admin",)


def _require_tenant(payload: dict) -> int:
    tenant_id: Optional[int] = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    return tenant_id


def _calc_priority(
    amount_owed: Optional[Decimal], months_overdue: Optional[int]
) -> int:
    return int(float(amount_owed or 0) * 0.4 + float(months_overdue or 0) * 0.3)


def _case_row_to_response(
    case: CollectionCase, owner: OwnerProfile
) -> CaseWithOwnerResponse:
    return CaseWithOwnerResponse(
        id=case.id,
        tenant_id=case.tenant_id,
        project_id=case.project_id,
        owner=OwnerInfo(
            id=owner.id,
            name=owner.name,
            phone_masked=mask_phone(owner.phone_enc),  # phone_enc is plaintext until AES sprint
            building=owner.building,
            room=owner.room,
            do_not_call=owner.do_not_call,
        ),
        assigned_to=case.assigned_to,
        pool_type=case.pool_type,
        stage=case.stage,
        amount_owed=case.amount_owed,
        months_overdue=case.months_overdue,
        priority_score=case.priority_score,
        last_contact_at=case.last_contact_at,
        monthly_contact_count=case.monthly_contact_count,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.post("/cases/import", response_model=CaseImportResponse, status_code=201)
async def import_cases(
    body: CaseImportRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseImportResponse:
    tenant_id = _require_tenant(payload)
    imported = 0

    for row in body.rows:
        existing_owner = db.execute(
            select(OwnerProfile).where(
                OwnerProfile.tenant_id == tenant_id,
                OwnerProfile.phone_enc == row.phone,
            )
        ).scalar_one_or_none()

        if existing_owner is None:
            owner = OwnerProfile(
                tenant_id=tenant_id,
                name=row.name,
                phone_enc=row.phone,  # plaintext until AES sprint
                building=row.building,
                room=row.room,
            )
            db.add(owner)
            db.flush()
        else:
            owner = existing_owner

        case = CollectionCase(
            tenant_id=tenant_id,
            owner_id=owner.id,
            pool_type="public",
            stage="new",
            amount_owed=row.amount_owed,
            months_overdue=row.months_overdue,
            priority_score=_calc_priority(row.amount_owed, row.months_overdue),
        )
        db.add(case)
        imported += 1

    db.flush()
    db.commit()
    return CaseImportResponse(imported=imported, skipped=0, errors=[])


@router.get("/cases", response_model=PaginatedResponse[CaseWithOwnerResponse])
async def list_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    stage: Optional[str] = Query(None),
    pool_type: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CaseWithOwnerResponse]:
    tenant_id = _require_tenant(payload)

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

    return PaginatedResponse(
        items=[_case_row_to_response(case, owner) for case, owner in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/cases/{case_id}", response_model=CaseWithOwnerResponse)
async def get_case(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseWithOwnerResponse:
    tenant_id = _require_tenant(payload)
    row = db.execute(
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(
            CollectionCase.id == case_id,
            CollectionCase.tenant_id == tenant_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    return _case_row_to_response(row[0], row[1])
