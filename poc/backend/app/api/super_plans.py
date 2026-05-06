"""Sprint 15 — PlanConfig CRUD for platform_super.

GET    /api/v1/super/plans
GET    /api/v1/super/plans/{id}
POST   /api/v1/super/plans
PATCH  /api/v1/super/plans/{id}
PATCH  /api/v1/super/plans/{id}/active
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_roles
from app.models.audit import PlanConfig
from app.models.user import UserAccount
from app.schemas.plan import (
    PlanConfigActiveIn,
    PlanConfigCreate,
    PlanConfigOut,
    PlanConfigPatch,
)

router = APIRouter()

SUPER_ROLES = ("platform_super", "platform_superadmin")


def _load_plan(db: Session, plan_id: int) -> PlanConfig:
    plan = db.get(PlanConfig, plan_id)
    if plan is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "套餐不存在"},
        )
    return plan


@router.get("/plans", response_model=list[PlanConfigOut])
async def list_plans(
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[PlanConfigOut]:
    rows = (
        db.execute(select(PlanConfig).order_by(PlanConfig.id.asc()))
        .scalars()
        .all()
    )
    return [PlanConfigOut.model_validate(r) for r in rows]


@router.get("/plans/{plan_id}", response_model=PlanConfigOut)
async def get_plan(
    plan_id: int,
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PlanConfigOut:
    plan = _load_plan(db, plan_id)
    return PlanConfigOut.model_validate(plan)


@router.post("/plans", response_model=PlanConfigOut, status_code=201)
async def create_plan(
    body: PlanConfigCreate,
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PlanConfigOut:
    plan = PlanConfig(
        plan_name=body.plan_name,
        display_name=body.display_name,
        monthly_minutes=body.monthly_minutes,
        price_monthly=body.price_monthly,
        features=body.features,
        is_active=body.is_active,
    )
    db.add(plan)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_DUPLICATE_PLAN_NAME",
                "message": "套餐编码已存在",
            },
        ) from None
    db.commit()
    db.refresh(plan)
    return PlanConfigOut.model_validate(plan)


@router.patch("/plans/{plan_id}", response_model=PlanConfigOut)
async def patch_plan(
    plan_id: int,
    body: PlanConfigPatch,
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PlanConfigOut:
    plan = _load_plan(db, plan_id)
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(plan, field, value)
    db.commit()
    db.refresh(plan)
    return PlanConfigOut.model_validate(plan)


@router.patch("/plans/{plan_id}/active", response_model=PlanConfigOut)
async def toggle_plan_active(
    plan_id: int,
    body: PlanConfigActiveIn,
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PlanConfigOut:
    plan = _load_plan(db, plan_id)
    plan.is_active = body.is_active
    db.commit()
    db.refresh(plan)
    return PlanConfigOut.model_validate(plan)
