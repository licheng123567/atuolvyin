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
from app.models.legal_platform_invoice import LegalPlatformInvoice
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.legal_conversion import LegalConversionOrderOut
from app.schemas.legal_invoice import (
    ConfirmInvoiceRequest,
    GenerateInvoiceRequest,
    LegalPlatformInvoiceOut,
    MarkPaidRequest,
)
from app.services.legal_invoice import generate_invoice, total_unpaid_fee

router = APIRouter()

OPS_ROLES = ("platform_ops", "platform_super", "platform_superadmin")


def _order_to_out(order: LegalConversionOrder, package_name: str | None) -> LegalConversionOrderOut:
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
    stmt = select(LegalConversionOrder, LegalServicePackage.name).join(
        LegalServicePackage,
        LegalServicePackage.id == LegalConversionOrder.package_id,
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
        items=items,
        total=total,
        page=page,
        page_size=page_size,
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
        select(func.coalesce(func.sum(LegalConversionOrder.platform_fee_amount), 0)).where(
            LegalConversionOrder.law_firm_id == firm_id,
            LegalConversionOrder.status == "completed",
        )
    ).scalar_one()

    unpaid = total_unpaid_fee(db, law_firm_id=firm_id)
    return {
        "firm_id": firm_id,
        "firm_name": firm.name,
        "rating_avg": float(firm.rating_avg),
        "completed_orders": firm.completed_orders,
        "by_status": by_status,
        "platform_fee_total_completed": float(fee_total or 0),
        "platform_fee_unpaid": float(unpaid),
        "now": datetime.now(UTC).isoformat(),
    }


# ── Sprint 16.3 — 律所→平台介绍费账单 ────────────────────────────


@router.post(
    "/firms/{firm_id}/invoices",
    response_model=LegalPlatformInvoiceOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def generate_firm_invoice(
    firm_id: int,
    body: GenerateInvoiceRequest,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalPlatformInvoiceOut:
    """聚合 [period_start, period_end) 内 completed 订单 → DRAFT 账单（幂等）."""
    firm = db.get(LawFirm, firm_id)
    if firm is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "律所不存在"},
        )
    invoice, _created = generate_invoice(
        db,
        law_firm_id=firm_id,
        period_start=body.period_start,
        period_end=body.period_end,
    )
    db.commit()
    db.refresh(invoice)
    return LegalPlatformInvoiceOut.model_validate(invoice)


@router.get(
    "/firms/{firm_id}/invoices",
    response_model=PaginatedResponse[LegalPlatformInvoiceOut],
)
async def list_firm_invoices(
    firm_id: int,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = Query(None, max_length=16),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[LegalPlatformInvoiceOut]:
    firm = db.get(LawFirm, firm_id)
    if firm is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "律所不存在"},
        )
    stmt = select(LegalPlatformInvoice).where(LegalPlatformInvoice.law_firm_id == firm_id)
    if status:
        stmt = stmt.where(LegalPlatformInvoice.status == status)
    stmt = stmt.order_by(LegalPlatformInvoice.period_start.desc())

    total_stmt = select(func.count(LegalPlatformInvoice.id)).where(
        LegalPlatformInvoice.law_firm_id == firm_id
    )
    if status:
        total_stmt = total_stmt.where(LegalPlatformInvoice.status == status)
    total = int(db.execute(total_stmt).scalar_one())

    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return PaginatedResponse[LegalPlatformInvoiceOut](
        items=[LegalPlatformInvoiceOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/invoices/{invoice_id}/confirm",
    response_model=LegalPlatformInvoiceOut,
)
async def confirm_invoice(
    invoice_id: int,
    body: ConfirmInvoiceRequest,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalPlatformInvoiceOut:
    invoice = db.get(LegalPlatformInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "账单不存在"},
        )
    if invoice.status != "DRAFT":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATUS",
                "message": f"账单状态 {invoice.status}，无法 confirm",
            },
        )
    invoice.status = "CONFIRMED"
    invoice.confirmed_at = datetime.now(UTC)
    if body.notes:
        invoice.notes = body.notes
    db.commit()
    db.refresh(invoice)
    return LegalPlatformInvoiceOut.model_validate(invoice)


@router.post(
    "/invoices/{invoice_id}/paid",
    response_model=LegalPlatformInvoiceOut,
)
async def mark_invoice_paid(
    invoice_id: int,
    body: MarkPaidRequest,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalPlatformInvoiceOut:
    invoice = db.get(LegalPlatformInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "账单不存在"},
        )
    if invoice.status != "CONFIRMED":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATUS",
                "message": f"账单状态 {invoice.status}，无法标记 PAID",
            },
        )
    invoice.status = "PAID"
    invoice.paid_at = datetime.now(UTC)
    if body.payment_proof_url:
        invoice.payment_proof_url = body.payment_proof_url
    if body.notes:
        invoice.notes = (invoice.notes + "\n" if invoice.notes else "") + body.notes
    db.commit()
    db.refresh(invoice)
    return LegalPlatformInvoiceOut.model_validate(invoice)


@router.post(
    "/invoices/{invoice_id}/cancel",
    response_model=LegalPlatformInvoiceOut,
)
async def cancel_invoice(
    invoice_id: int,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalPlatformInvoiceOut:
    invoice = db.get(LegalPlatformInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "账单不存在"},
        )
    if invoice.status not in ("DRAFT", "CONFIRMED"):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATUS",
                "message": f"账单状态 {invoice.status}，无法取消",
            },
        )
    invoice.status = "CANCELLED"
    db.commit()
    db.refresh(invoice)
    return LegalPlatformInvoiceOut.model_validate(invoice)
