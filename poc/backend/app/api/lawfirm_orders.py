"""v1.5.7 S2 — 律所代表工作台 API (PRD §20.4)。

GET    /api/v1/lawfirm/orders                            列出派给当前用户所属律所的订单
GET    /api/v1/lawfirm/orders/{id}                       订单详情
POST   /api/v1/lawfirm/orders/{id}/assign-lawyer         律所代表分配律师 → in_service

身份解析：登录用户经 require_roles('legal') 后，从 law_firm_membership 表查 role_in_firm='admin'
的活跃记录决定本人代表的律所。一个用户可代表多个律所，本批次只支持单律所（取第一条）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.law_firm import LawFirm, LawFirmLawyer
from app.models.law_firm_membership import LawFirmMembership
from app.models.legal_conversion import LegalConversionOrder
from app.services.legal_order_enrich import enrich_order

router = APIRouter()

LEGAL_ROLES = ("legal",)


def _resolve_law_firm_for_user(
    db: Session, user_id: int, role_in_firm: str = "admin"
) -> LawFirmMembership:
    stmt = (
        select(LawFirmMembership)
        .where(LawFirmMembership.user_id == user_id)
        .where(LawFirmMembership.role_in_firm == role_in_firm)
        .where(LawFirmMembership.is_active.is_(True))
        .order_by(LawFirmMembership.id)
    )
    membership = db.execute(stmt).scalars().first()
    if not membership:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ERR_NOT_LAW_FIRM_REPRESENTATIVE",
                "message": "当前用户未注册为任何律所代表",
            },
        )
    return membership


@router.get("/orders")
async def list_lawfirm_orders(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    status: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict:
    user_id = int(payload["user_id"])
    membership = _resolve_law_firm_for_user(db, user_id, role_in_firm="admin")

    stmt = (
        select(LegalConversionOrder)
        .where(LegalConversionOrder.law_firm_id == membership.law_firm_id)
        .order_by(LegalConversionOrder.id.desc())
    )
    if status:
        stmt = stmt.where(LegalConversionOrder.status == status)
    total = len(db.execute(stmt.with_only_columns(LegalConversionOrder.id)).all())
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return {
        "items": [enrich_order(db, r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/orders/{order_id}")
async def get_lawfirm_order(
    order_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    user_id = int(payload["user_id"])
    membership = _resolve_law_firm_for_user(db, user_id, role_in_firm="admin")
    order = db.get(LegalConversionOrder, order_id)
    if not order or order.law_firm_id != membership.law_firm_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "订单不存在或不属于本所"},
        )
    return enrich_order(db, order)


@router.post("/orders/{order_id}/assign-lawyer")
async def assign_lawyer_to_order(
    order_id: int,
    body: dict,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """body = {"lawyer_id": int}"""
    lawyer_id = body.get("lawyer_id")
    if not isinstance(lawyer_id, int):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_VALIDATION", "message": "缺少 lawyer_id"},
        )
    user_id = int(payload["user_id"])
    membership = _resolve_law_firm_for_user(db, user_id, role_in_firm="admin")
    order = db.get(LegalConversionOrder, order_id)
    if not order or order.law_firm_id != membership.law_firm_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "订单不存在或不属于本所"},
        )
    if order.status != "dispatched":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATE",
                "message": f"订单当前状态为 {order.status}，仅 dispatched 可分律师",
            },
        )
    lawyer = db.get(LawFirmLawyer, lawyer_id)
    if not lawyer or lawyer.law_firm_id != membership.law_firm_id:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_LAWYER_NOT_IN_FIRM", "message": "该律师不属于本所"},
        )
    if not lawyer.is_active:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_LAWYER_INACTIVE", "message": "该律师已停用"},
        )
    order.lawyer_id = lawyer.id
    order.assigned_lawyer_name = lawyer.name
    order.status = "in_service"
    order.dispatched_at = order.dispatched_at or datetime.now(UTC)
    db.add(order)
    db.commit()
    db.refresh(order)
    return enrich_order(db, order)


@router.get("/lawyers", response_model=list[dict])
async def list_lawyers_in_my_firm(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    """律所代表分律师下拉用：列出本所所有 active 律师。"""
    user_id = int(payload["user_id"])
    membership = _resolve_law_firm_for_user(db, user_id, role_in_firm="admin")
    rows = (
        db.execute(
            select(LawFirmLawyer)
            .where(LawFirmLawyer.law_firm_id == membership.law_firm_id)
            .where(LawFirmLawyer.is_active.is_(True))
            .order_by(LawFirmLawyer.id)
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": lawyer.id,
            "name": lawyer.name,
            "specialties": lawyer.specialties or [],
            "phone": lawyer.phone,
        }
        for lawyer in rows
    ]


@router.get("/me", response_model=dict)
async def get_lawfirm_context(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """返回当前登录用户代表的律所基本信息。"""
    user_id = int(payload["user_id"])
    membership = _resolve_law_firm_for_user(db, user_id, role_in_firm="admin")
    firm = db.get(LawFirm, membership.law_firm_id)
    if not firm:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_LAW_FIRM_NOT_FOUND", "message": "关联律所不存在"},
        )
    return {
        "law_firm_id": firm.id,
        "law_firm_name": firm.name,
        "region": firm.region,
        "rating_avg": float(firm.rating_avg),
        "completed_orders": firm.completed_orders,
    }
