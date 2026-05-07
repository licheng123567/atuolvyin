"""Sprint 16.1 — 法务转化通道 admin API (PRD §20.4)。

GET    /api/v1/admin/legal-packages                          列出可用服务包
GET    /api/v1/admin/cases/{case_id}/legal-conversion-preview 预览时间线+推荐
POST   /api/v1/admin/cases/{case_id}/convert-to-legal        创建转化订单
GET    /api/v1/admin/legal-conversion-orders                 订单列表
GET    /api/v1/admin/legal-conversion-orders/{id}            订单详情
POST   /api/v1/admin/legal-conversion-orders/{id}/dispatch   平台 ops 撮合律所
POST   /api/v1/admin/legal-conversion-orders/{id}/complete   律所标记完成
POST   /api/v1/admin/legal-conversion-orders/{id}/cancel     物业取消
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.case import CollectionCase
from app.models.law_firm import LawFirm, LawFirmLawyer
from app.models.legal_conversion import LegalConversionOrder, LegalServicePackage
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.legal_conversion import (
    CompleteOrderRequest,
    ConvertCasePreviewOut,
    ConvertCaseRequest,
    DispatchOrderRequest,
    LegalConversionOrderOut,
    LegalServicePackageOut,
)
from app.services.legal_conversion import (
    build_timeline_summary,
    estimate_cost,
    recommend_package,
)

router = APIRouter()

ADMIN_ROLES = ("admin",)
PLATFORM_OPS_ROLES = ("platform_ops", "platform_super", "platform_superadmin")


def _require_tenant(payload: dict) -> int:
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    return int(tenant_id)


def _enabled_packages(db: Session, tenant_id: int) -> list[LegalServicePackage]:
    """全局（tenant_id IS NULL）+ 本租户 enabled 包，按 sort_order。"""
    rows = db.execute(
        select(LegalServicePackage)
        .where(
            LegalServicePackage.enabled.is_(True),
            or_(
                LegalServicePackage.tenant_id.is_(None),
                LegalServicePackage.tenant_id == tenant_id,
            ),
        )
        .order_by(LegalServicePackage.sort_order, LegalServicePackage.id)
    ).scalars().all()
    return list(rows)


def _order_to_out(
    order: LegalConversionOrder, package_name: str | None = None
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


# ── 服务包目录 ───────────────────────────────────────────────────


@router.get("/legal-packages", response_model=list[LegalServicePackageOut])
async def list_legal_packages(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[LegalServicePackageOut]:
    tenant_id = _require_tenant(payload)
    return [LegalServicePackageOut.model_validate(p) for p in _enabled_packages(db, tenant_id)]


# ── 案件 → 法务转化预览（Dry-run）─────────────────────────────────


@router.get(
    "/cases/{case_id}/legal-conversion-preview",
    response_model=ConvertCasePreviewOut,
)
async def preview_case_conversion(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ConvertCasePreviewOut:
    tenant_id = _require_tenant(payload)
    case = db.get(CollectionCase, case_id)
    if case is None or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    timeline = build_timeline_summary(db, case=case)
    recommendation = recommend_package(
        amount_owed=case.amount_owed,
        months_overdue=case.months_overdue,
        contact_count=int(timeline.get("total_calls") or 0),
    )
    packages = _enabled_packages(db, tenant_id)
    return ConvertCasePreviewOut(
        timeline_summary=timeline,
        recommendation=recommendation,
        available_packages=[LegalServicePackageOut.model_validate(p) for p in packages],
    )


# ── 创建订单 ─────────────────────────────────────────────────────


@router.post(
    "/cases/{case_id}/convert-to-legal",
    response_model=LegalConversionOrderOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def convert_case_to_legal(
    case_id: int,
    body: ConvertCaseRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionOrderOut:
    tenant_id = _require_tenant(payload)
    case = db.get(CollectionCase, case_id)
    if case is None or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )

    package = db.get(LegalServicePackage, body.package_id)
    if (
        package is None
        or not package.enabled
        or (package.tenant_id is not None and package.tenant_id != tenant_id)
    ):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_PACKAGE_INVALID", "message": "服务包不可用"},
        )

    # 同案件 active 订单去重
    existing = db.execute(
        select(LegalConversionOrder).where(
            LegalConversionOrder.case_id == case_id,
            LegalConversionOrder.status.in_(("pending", "dispatched", "in_service")),
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_ORDER_EXISTS",
                "message": "该案件已存在进行中的法务转化订单",
            },
        )

    timeline = build_timeline_summary(db, case=case)
    recommendation = recommend_package(
        amount_owed=case.amount_owed,
        months_overdue=case.months_overdue,
        contact_count=int(timeline.get("total_calls") or 0),
    )
    cost = estimate_cost(package=package, amount_owed=case.amount_owed)

    platform_fee = (package.price * package.platform_fee_rate).quantize(Decimal("0.01"))
    order = LegalConversionOrder(
        tenant_id=tenant_id,
        case_id=case.id,
        package_id=package.id,
        status="pending",
        price_quoted=package.price,
        platform_fee_amount=platform_fee,
        timeline_summary=timeline,
        recommendation=recommendation,
        cost_estimate=cost,
        notes=body.notes,
        created_by=int(payload.get("user_id") or 0) or None,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return _order_to_out(order, package.name)


# ── 订单列表 / 详情 ──────────────────────────────────────────────


@router.get(
    "/legal-conversion-orders",
    response_model=PaginatedResponse[LegalConversionOrderOut],
)
async def list_orders(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = Query(None, max_length=32),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[LegalConversionOrderOut]:
    tenant_id = _require_tenant(payload)
    stmt = (
        select(LegalConversionOrder, LegalServicePackage.name)
        .join(LegalServicePackage, LegalServicePackage.id == LegalConversionOrder.package_id)
        .where(LegalConversionOrder.tenant_id == tenant_id)
    )
    if status:
        stmt = stmt.where(LegalConversionOrder.status == status)
    stmt = stmt.order_by(LegalConversionOrder.id.desc())
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()

    from sqlalchemy import func as _f
    total_stmt = select(_f.count(LegalConversionOrder.id)).where(
        LegalConversionOrder.tenant_id == tenant_id
    )
    if status:
        total_stmt = total_stmt.where(LegalConversionOrder.status == status)
    total = int(db.execute(total_stmt).scalar_one())

    items = [_order_to_out(o, name) for o, name in rows]
    return PaginatedResponse[LegalConversionOrderOut](
        items=items, total=total, page=page, page_size=page_size,
    )


@router.get(
    "/legal-conversion-orders/{order_id}",
    response_model=LegalConversionOrderOut,
)
async def get_order(
    order_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionOrderOut:
    tenant_id = _require_tenant(payload)
    row = db.execute(
        select(LegalConversionOrder, LegalServicePackage.name)
        .join(LegalServicePackage, LegalServicePackage.id == LegalConversionOrder.package_id)
        .where(
            LegalConversionOrder.id == order_id,
            LegalConversionOrder.tenant_id == tenant_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "订单不存在"},
        )
    return _order_to_out(row[0], row[1])


# ── 状态流转 ─────────────────────────────────────────────────────


@router.post(
    "/legal-conversion-orders/{order_id}/dispatch",
    response_model=LegalConversionOrderOut,
)
async def dispatch_order(
    order_id: int,
    body: DispatchOrderRequest,
    _user: Annotated[UserAccount, Depends(require_roles(*PLATFORM_OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionOrderOut:
    """平台 ops 撮合律所（不限 tenant，因为是平台动作）。"""
    order = db.get(LegalConversionOrder, order_id)
    if order is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "订单不存在"},
        )
    if order.status != "pending":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATUS",
                "message": f"订单当前状态 {order.status}，无法 dispatch",
            },
        )

    # 律所池模式（优先）：解析 law_firm_id + lawyer_id，denormalize 名字快照
    firm_name: str | None = None
    lawyer_name: str | None = None
    if body.law_firm_id is not None:
        firm = db.get(LawFirm, body.law_firm_id)
        if firm is None or not firm.enabled or not firm.accepting_orders:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"code": "ERR_FIRM_INVALID", "message": "律所不可用或未开启接单"},
            )
        firm_name = firm.name
        order.law_firm_id = firm.id

        if body.lawyer_id is not None:
            lawyer = db.get(LawFirmLawyer, body.lawyer_id)
            if (
                lawyer is None
                or lawyer.law_firm_id != firm.id
                or not lawyer.is_active
            ):
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail={"code": "ERR_LAWYER_INVALID", "message": "律师不属于该律所或已停用"},
                )
            lawyer_name = lawyer.name
            order.lawyer_id = lawyer.id
    else:
        # 回落 free-text（要求至少 assigned_law_firm 非空）
        if not body.assigned_law_firm or len(body.assigned_law_firm.strip()) < 2:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "ERR_VALIDATION", "message": "需提供 law_firm_id 或 assigned_law_firm"},
            )
        firm_name = body.assigned_law_firm.strip()
        lawyer_name = (body.assigned_lawyer_name or "").strip() or None

    order.status = "dispatched"
    order.assigned_law_firm = firm_name
    order.assigned_lawyer_name = lawyer_name
    order.dispatched_at = datetime.now(UTC)
    db.commit()
    db.refresh(order)

    pkg = db.get(LegalServicePackage, order.package_id)
    return _order_to_out(order, pkg.name if pkg else None)


@router.post(
    "/legal-conversion-orders/{order_id}/complete",
    response_model=LegalConversionOrderOut,
)
async def complete_order(
    order_id: int,
    body: CompleteOrderRequest,
    _user: Annotated[UserAccount, Depends(require_roles(*PLATFORM_OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionOrderOut:
    order = db.get(LegalConversionOrder, order_id)
    if order is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "订单不存在"},
        )
    if order.status not in ("dispatched", "in_service"):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATUS",
                "message": f"订单当前状态 {order.status}，无法 complete",
            },
        )
    order.status = "completed"
    order.completed_at = datetime.now(UTC)
    if body.notes:
        order.notes = (order.notes + "\n" if order.notes else "") + body.notes
    # 律所完成单数 +1（撮合质量后续可基于此排名）
    if order.law_firm_id is not None:
        firm = db.get(LawFirm, order.law_firm_id)
        if firm is not None:
            firm.completed_orders = (firm.completed_orders or 0) + 1
    db.commit()
    db.refresh(order)

    pkg = db.get(LegalServicePackage, order.package_id)
    return _order_to_out(order, pkg.name if pkg else None)


@router.post(
    "/legal-conversion-orders/{order_id}/cancel",
    response_model=LegalConversionOrderOut,
)
async def cancel_order(
    order_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionOrderOut:
    tenant_id = _require_tenant(payload)
    order = db.get(LegalConversionOrder, order_id)
    if order is None or order.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "订单不存在"},
        )
    if order.status not in ("pending", "dispatched"):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATUS",
                "message": f"订单当前状态 {order.status}，无法取消",
            },
        )
    order.status = "cancelled"
    db.commit()
    db.refresh(order)

    pkg = db.get(LegalServicePackage, order.package_id)
    return _order_to_out(order, pkg.name if pkg else None)
