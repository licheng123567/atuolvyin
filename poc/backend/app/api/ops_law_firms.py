"""Sprint 16.2 — 律所池 + 律师 (PRD §20.4)。

仅平台 ops 管理；POST /dispatch 时从该池中选取，denormalize 到订单表。

GET    /api/v1/ops/law-firms                  list (q + region + accepting filter)
POST   /api/v1/ops/law-firms                  create
GET    /api/v1/ops/law-firms/{id}             detail incl. lawyers
PATCH  /api/v1/ops/law-firms/{id}             partial update
DELETE /api/v1/ops/law-firms/{id}             soft delete (enabled=False)
POST   /api/v1/ops/law-firms/{id}/lawyers     add lawyer
PATCH  /api/v1/ops/law-firms/{id}/lawyers/{lid}
DELETE /api/v1/ops/law-firms/{id}/lawyers/{lid}
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi import status as http_status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_roles
from app.models.law_firm import LawFirm, LawFirmLawyer
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.law_firm import (
    LawFirmCreate,
    LawFirmLawyerOut,
    LawFirmOut,
    LawFirmPatch,
    LawyerCreate,
    LawyerPatch,
)

router = APIRouter()

OPS_ROLES = ("platform_ops", "platform_super", "platform_superadmin")


def _firm_with_lawyers(db: Session, firm: LawFirm) -> LawFirmOut:
    lawyers = (
        db.execute(
            select(LawFirmLawyer)
            .where(LawFirmLawyer.law_firm_id == firm.id)
            .order_by(LawFirmLawyer.id)
        )
        .scalars()
        .all()
    )
    out = LawFirmOut.model_validate(firm)
    out.lawyers = [LawFirmLawyerOut.model_validate(lawyer) for lawyer in lawyers]
    return out


@router.get("/law-firms", response_model=PaginatedResponse[LawFirmOut])
async def list_law_firms(
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None, max_length=200),
    region: str | None = Query(None, max_length=64),
    accepting: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[LawFirmOut]:
    stmt = select(LawFirm)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(LawFirm.name.ilike(like), LawFirm.license_no.ilike(like)))
    if region:
        stmt = stmt.where(LawFirm.region == region)
    if accepting is True:
        stmt = stmt.where(LawFirm.enabled.is_(True), LawFirm.accepting_orders.is_(True))
    stmt = stmt.order_by(LawFirm.id.desc())
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()

    from sqlalchemy import func as _f

    total_stmt = select(_f.count(LawFirm.id))
    if q:
        like = f"%{q}%"
        total_stmt = total_stmt.where(or_(LawFirm.name.ilike(like), LawFirm.license_no.ilike(like)))
    if region:
        total_stmt = total_stmt.where(LawFirm.region == region)
    if accepting is True:
        total_stmt = total_stmt.where(LawFirm.enabled.is_(True), LawFirm.accepting_orders.is_(True))
    total = int(db.execute(total_stmt).scalar_one())

    return PaginatedResponse[LawFirmOut](
        items=[_firm_with_lawyers(db, f) for f in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/law-firms",
    response_model=LawFirmOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_law_firm(
    body: LawFirmCreate,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LawFirmOut:
    firm = LawFirm(**body.model_dump(exclude_none=True))
    db.add(firm)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_LICENSE_DUPLICATE", "message": "执业证号重复"},
        ) from exc
    db.refresh(firm)
    return _firm_with_lawyers(db, firm)


@router.get("/law-firms/{firm_id}", response_model=LawFirmOut)
async def get_law_firm(
    firm_id: int,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LawFirmOut:
    firm = db.get(LawFirm, firm_id)
    if firm is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "律所不存在"},
        )
    return _firm_with_lawyers(db, firm)


@router.patch("/law-firms/{firm_id}", response_model=LawFirmOut)
async def patch_law_firm(
    firm_id: int,
    body: LawFirmPatch,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LawFirmOut:
    firm = db.get(LawFirm, firm_id)
    if firm is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "律所不存在"},
        )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(firm, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_LICENSE_DUPLICATE", "message": "执业证号重复"},
        ) from exc
    db.refresh(firm)
    return _firm_with_lawyers(db, firm)


@router.delete(
    "/law-firms/{firm_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def delete_law_firm(
    firm_id: int,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    firm = db.get(LawFirm, firm_id)
    if firm is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "律所不存在"},
        )
    # 软删除：保留历史数据，仅停用
    firm.enabled = False
    firm.accepting_orders = False
    db.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


# ── lawyers ──────────────────────────────────────────────────────


@router.post(
    "/law-firms/{firm_id}/lawyers",
    response_model=LawFirmLawyerOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def add_lawyer(
    firm_id: int,
    body: LawyerCreate,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LawFirmLawyerOut:
    firm = db.get(LawFirm, firm_id)
    if firm is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "律所不存在"},
        )
    lawyer = LawFirmLawyer(law_firm_id=firm.id, **body.model_dump(exclude_none=True))
    db.add(lawyer)
    db.commit()
    db.refresh(lawyer)
    return LawFirmLawyerOut.model_validate(lawyer)


@router.patch(
    "/law-firms/{firm_id}/lawyers/{lawyer_id}",
    response_model=LawFirmLawyerOut,
)
async def patch_lawyer(
    firm_id: int,
    lawyer_id: int,
    body: LawyerPatch,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LawFirmLawyerOut:
    lawyer = db.get(LawFirmLawyer, lawyer_id)
    if lawyer is None or lawyer.law_firm_id != firm_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "律师不存在"},
        )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(lawyer, field, value)
    db.commit()
    db.refresh(lawyer)
    return LawFirmLawyerOut.model_validate(lawyer)


@router.delete(
    "/law-firms/{firm_id}/lawyers/{lawyer_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def remove_lawyer(
    firm_id: int,
    lawyer_id: int,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    lawyer = db.get(LawFirmLawyer, lawyer_id)
    if lawyer is None or lawyer.law_firm_id != firm_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "律师不存在"},
        )
    # 软删
    lawyer.is_active = False
    db.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
