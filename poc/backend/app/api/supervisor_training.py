"""v0.6.0 — 督导培训案例库 CRUD API。

GET    /supervisor/training-cases                  分页列表(按 category / source 过滤)
POST   /supervisor/training-cases                  督导手工录入(source=manual)
GET    /supervisor/training-cases/{id}             详情
PATCH  /supervisor/training-cases/{id}             更新(rating / lesson 编辑)
POST   /supervisor/training-cases/{id}/view        +1 学习计数
DELETE /supervisor/training-cases/{id}             删除(限创建者或 admin)
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_tenant_roles
from app.models.training_case import TrainingCase
from app.models.user import UserAccount
from app.schemas.training import (
    TrainingCaseCreateIn,
    TrainingCaseListResp,
    TrainingCaseOut,
)

router = APIRouter()

SUPERVISOR_ROLES = ("supervisor", "admin", "superadmin")


def _require_tenant(payload: dict) -> int:
    tid = payload.get("tenant_id")
    if not tid:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )
    return int(tid)


def _to_out(db: Session, tc: TrainingCase) -> TrainingCaseOut:
    creator_name: str | None = None
    if tc.created_by:
        u = db.get(UserAccount, tc.created_by)
        creator_name = u.name if u else None
    return TrainingCaseOut(
        id=tc.id,
        tenant_id=tc.tenant_id,
        title=tc.title,
        category=tc.category,  # type: ignore[arg-type]
        scenario=tc.scenario,
        lesson=tc.lesson,
        raw_call_id=tc.raw_call_id,
        raw_risk_event_id=tc.raw_risk_event_id,
        source=tc.source,  # type: ignore[arg-type]
        created_by=tc.created_by,
        created_by_name=creator_name,
        rating=tc.rating,
        views=tc.views,
        created_at=tc.created_at,
        updated_at=tc.updated_at,
    )


@router.get("/training-cases", response_model=TrainingCaseListResp)
def list_training_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    category: Literal["negotiate", "escalate", "objection", "investigate"] | None = None,
    source: Literal["auto", "manual"] | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
) -> TrainingCaseListResp:
    """列出本租户培训案例,可按 category / source 过滤;按创建时间倒序。"""
    tenant_id = _require_tenant(payload)
    stmt = select(TrainingCase).where(TrainingCase.tenant_id == tenant_id)
    if category:
        stmt = stmt.where(TrainingCase.category == category)
    if source:
        stmt = stmt.where(TrainingCase.source == source)

    total = db.execute(
        select(func.count(TrainingCase.id))
        .where(TrainingCase.tenant_id == tenant_id)
        .where(TrainingCase.category == category if category else True)  # type: ignore[arg-type]
        .where(TrainingCase.source == source if source else True)  # type: ignore[arg-type]
    ).scalar_one()

    rows = (
        db.execute(
            stmt.order_by(TrainingCase.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return TrainingCaseListResp(
        items=[_to_out(db, r) for r in rows],
        total=int(total or 0),
    )


@router.post(
    "/training-cases",
    response_model=TrainingCaseOut,
    status_code=http_status.HTTP_201_CREATED,
)
def create_training_case(
    body: TrainingCaseCreateIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TrainingCaseOut:
    """督导手工录入培训案例。"""
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)

    tc = TrainingCase(
        tenant_id=tenant_id,
        title=body.title,
        category=body.category,
        scenario=body.scenario,
        lesson=body.lesson,
        raw_call_id=body.raw_call_id,
        source="manual",
        created_by=user_id or None,
        rating=body.rating,
    )
    db.add(tc)
    db.commit()
    db.refresh(tc)
    return _to_out(db, tc)


@router.get("/training-cases/{tc_id}", response_model=TrainingCaseOut)
def get_training_case(
    tc_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TrainingCaseOut:
    tenant_id = _require_tenant(payload)
    tc = db.get(TrainingCase, tc_id)
    if tc is None or tc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "培训案例不存在"},
        )
    return _to_out(db, tc)


class TrainingCasePatchIn(BaseModel):
    title: str | None = Field(None, max_length=256)
    lesson: str | None = Field(None, max_length=4000)
    rating: int | None = Field(None, ge=0, le=5)


@router.patch("/training-cases/{tc_id}", response_model=TrainingCaseOut)
def update_training_case(
    tc_id: int,
    body: TrainingCasePatchIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TrainingCaseOut:
    tenant_id = _require_tenant(payload)
    tc = db.get(TrainingCase, tc_id)
    if tc is None or tc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "培训案例不存在"},
        )

    if body.title is not None:
        tc.title = body.title
    if body.lesson is not None:
        tc.lesson = body.lesson
    if body.rating is not None:
        tc.rating = body.rating

    db.commit()
    db.refresh(tc)
    return _to_out(db, tc)


@router.post("/training-cases/{tc_id}/view", response_model=TrainingCaseOut)
def increment_views(
    tc_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TrainingCaseOut:
    """每次「学过」点击 +1。轻量端点,不写 audit。"""
    tenant_id = _require_tenant(payload)
    tc = db.get(TrainingCase, tc_id)
    if tc is None or tc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "培训案例不存在"},
        )
    tc.views = (tc.views or 0) + 1
    db.commit()
    db.refresh(tc)
    return _to_out(db, tc)


@router.delete("/training-cases/{tc_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_training_case(
    tc_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    tenant_id = _require_tenant(payload)
    role = str(payload.get("role") or "")
    user_id = int(payload.get("user_id") or 0)

    tc = db.get(TrainingCase, tc_id)
    if tc is None or tc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "培训案例不存在"},
        )
    # 只有创建者或物业管理员可删
    if role != "admin" and tc.created_by != user_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "仅创建者或物业管理员可删除"},
        )
    db.delete(tc)
    db.commit()
