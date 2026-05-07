"""Sprint 16.2 — 法务工作台 (PRD §20.4)。

平台 ops 视角，按律所筛选转化订单 + 推动状态机
（dispatched → in_service）。律所外部接入用独立账号体系，本 sprint 暂不做。

GET   /api/v1/legal-workstation/orders                 列出（按 law_firm_id 过滤）
POST  /api/v1/legal-workstation/orders/{id}/start      dispatched → in_service
GET   /api/v1/legal-workstation/firms/{id}/stats       律所聚合统计
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_roles
from app.models.law_firm import LawFirm
from app.models.legal_conversion import LegalConversionOrder, LegalServicePackage
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.legal_conversion import LegalConversionOrderOut

router = APIRouter()

OPS_ROLES = ("platform_ops", "platform_super", "platform_superadmin")


def _order_to_out(
    order: LegalConversionOrder, package_name: str | None
) -> LegalConversionOrderOut:
    return LegalConversionOrderOut(
        id=order.id,
        tenant_id=order.tenant_id,
        case_id=order.case_id,
        package_id=order.package_id,
        package_name=package_name,
        status=order.status,
        price_quoted=order.price_quoted,
        platform_fee_amount=order.platform_fee_amount,
        assigned_law_firm=order.assigned_law_firm,
        assigned_lawyer_name=order.assigned_lawyer_name,
        timeline_summary=order.timeline_summary,
        recommendation=order.recommendation,
        cost_estimate=order.cost_estimate,
        notes=order.notes,
        created_by=order.created_by,
        dispatched_at=order.dispatched_at,
        completed_at=order.completed_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


@router.get(
    "/orders",
    response_model=PaginatedResponse[LegalConversionOrderOut],
)
async def list_workstation_orders(
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    law_firm_id: int | None = Query(None, gt=0),
    status: str | None = Query(None, max_length=32),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[LegalConversionOrderOut]:
    stmt = (
        select(LegalConversionOrder, LegalServicePackage.name)
        .join(
            LegalServicePackage,
            LegalServicePackage.id == LegalConversionOrder.package_id,
        )
    )
    if law_firm_id is not None:
        stmt = stmt.where(LegalConversionOrder.law_firm_id == law_firm_id)
    if status:
        stmt = stmt.where(LegalConversionOrder.status == status)
    stmt = stmt.order_by(LegalConversionOrder.id.desc())

    total_stmt = select(func.count(LegalConversionOrder.id))
    if law_firm_id is not None:
        total_stmt = total_stmt.where(LegalConversionOrder.law_firm_id == law_firm_id)
    if status:
        total_stmt = total_stmt.where(LegalConversionOrder.status == status)
    total = int(db.execute(total_stmt).scalar_one())

    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    items = [_order_to_out(o, name) for o, name in rows]
    return PaginatedResponse[LegalConversionOrderOut](
        items=items, total=total, page=page, page_size=page_size,
    )


@router.post(
    "/orders/{order_id}/start",
    response_model=LegalConversionOrderOut,
)
async def start_service(
    order_id: int,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionOrderOut:
    order = db.get(LegalConversionOrder, order_id)
    if order is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "订单不存在"},
        )
    if order.status != "dispatched":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATUS",
                "message": f"订单当前状态 {order.status}，无法 start",
            },
        )
    order.status = "in_service"
    db.commit()
    db.refresh(order)

    pkg = db.get(LegalServicePackage, order.package_id)
    return _order_to_out(order, pkg.name if pkg else None)


@router.get("/firms/{firm_id}/stats")
async def firm_stats(
    firm_id: int,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    firm = db.get(LawFirm, firm_id)
    if firm is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "律所不存在"},
        )
    rows = db.execute(
        select(LegalConversionOrder.status, func.count(LegalConversionOrder.id))
        .where(LegalConversionOrder.law_firm_id == firm_id)
        .group_by(LegalConversionOrder.status)
    ).all()
    by_status = {s: int(c) for s, c in rows}

    fee_total = db.execute(
        select(func.coalesce(func.sum(LegalConversionOrder.platform_fee_amount), 0))
        .where(
            LegalConversionOrder.law_firm_id == firm_id,
            LegalConversionOrder.status == "completed",
        )
    ).scalar_one()

    return {
        "firm_id": firm_id,
        "firm_name": firm.name,
        "rating_avg": float(firm.rating_avg),
        "completed_orders": firm.completed_orders,
        "by_status": by_status,
        "platform_fee_total_completed": float(fee_total or 0),
        "now": datetime.now(UTC).isoformat(),
    }
