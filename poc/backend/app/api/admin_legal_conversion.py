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
from app.models.legal_document_template import (
    LegalDocumentRender,
    LegalDocumentTemplate,
)
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
from app.schemas.legal_doc_render import (
    LegalDocumentRenderOut,
    LegalDocumentTemplateOut,
)
from app.services.legal_conversion import (
    build_timeline_summary,
    estimate_cost,
    recommend_package,
)
from app.services.legal_document_render import render_for_order

router = APIRouter()

ADMIN_ROLES = ("admin",)
PLATFORM_OPS_ROLES = ("ops", "superadmin")


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
    rows = (
        db.execute(
            select(LegalServicePackage)
            .where(
                LegalServicePackage.enabled.is_(True),
                or_(
                    LegalServicePackage.tenant_id.is_(None),
                    LegalServicePackage.tenant_id == tenant_id,
                ),
            )
            .order_by(LegalServicePackage.sort_order, LegalServicePackage.id)
        )
        .scalars()
        .all()
    )
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


def build_legal_conversion_order(
    db: Session,
    *,
    case: CollectionCase,
    package_id: int,
    notes: str | None,
    created_by_user_id: int | None,
    initial_status: str = "pending",
) -> LegalConversionOrder:
    """v1.6.8 — 共享 helper：校验 package + 去重已有 active 订单 + 创建 Order（不 commit）。

    被两处复用：
      1. `POST /admin/cases/{case_id}/convert-to-legal`（admin 直接建单 → status=pending → admin 撮合）
      2. `POST /legal-conversion-requests/{id}/approve`（督导审批通过 → status=internal_processing → 物业法务内部处理）

    v1.9.0 — initial_status 控制初始状态：
      - "pending" 走 admin 撮合律所链路（兼容老逻辑）
      - "internal_processing" 走物业法务内部处理链路（方案 B 新增）

    抛 HTTPException：400 服务包无效 / 409 已有 active 订单
    """
    tenant_id = case.tenant_id
    package = db.get(LegalServicePackage, package_id)
    if (
        package is None
        or not package.enabled
        or (package.tenant_id is not None and package.tenant_id != tenant_id)
    ):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_PACKAGE_INVALID", "message": "服务包不可用"},
        )

    existing = db.execute(
        select(LegalConversionOrder).where(
            LegalConversionOrder.case_id == case.id,
            # v1.9.0 — internal_processing 也算 active
            LegalConversionOrder.status.in_(
                ("pending", "dispatched", "in_service", "internal_processing")
            ),
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
        status=initial_status,
        price_quoted=package.price,
        platform_fee_amount=platform_fee,
        timeline_summary=timeline,
        recommendation=recommendation,
        cost_estimate=cost,
        notes=notes,
        created_by=created_by_user_id,
    )
    db.add(order)
    db.flush()  # populate order.id without committing parent transaction
    return order


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
    order = build_legal_conversion_order(
        db,
        case=case,
        package_id=body.package_id,
        notes=body.notes,
        created_by_user_id=int(payload.get("user_id") or 0) or None,
    )
    db.commit()
    db.refresh(order)
    package = db.get(LegalServicePackage, order.package_id)
    return _order_to_out(order, package.name if package else None)


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
        items=items,
        total=total,
        page=page,
        page_size=page_size,
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
            if lawyer is None or lawyer.law_firm_id != firm.id or not lawyer.is_active:
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
                detail={
                    "code": "ERR_VALIDATION",
                    "message": "需提供 law_firm_id 或 assigned_law_firm",
                },
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


# ── Sprint 16.4 — 法律文书渲染 ───────────────────────────────────


@router.get(
    "/legal-document-templates",
    response_model=list[LegalDocumentTemplateOut],
)
async def list_doc_templates(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[LegalDocumentTemplateOut]:
    """列出本租户可见模板（平台默认 + 本租户覆盖），按 package_type 排序。"""
    tenant_id = _require_tenant(payload)
    rows = (
        db.execute(
            select(LegalDocumentTemplate)
            .where(
                LegalDocumentTemplate.enabled.is_(True),
                or_(
                    LegalDocumentTemplate.tenant_id.is_(None),
                    LegalDocumentTemplate.tenant_id == tenant_id,
                ),
            )
            .order_by(LegalDocumentTemplate.package_type, LegalDocumentTemplate.id)
        )
        .scalars()
        .all()
    )
    return [LegalDocumentTemplateOut.model_validate(r) for r in rows]


def _get_order_for_tenant(db: Session, *, order_id: int, tenant_id: int) -> LegalConversionOrder:
    order = db.get(LegalConversionOrder, order_id)
    if order is None or order.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "订单不存在"},
        )
    return order


@router.get(
    "/legal-conversion-orders/{order_id}/document",
    response_model=LegalDocumentRenderOut,
)
async def get_latest_doc(
    order_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalDocumentRenderOut:
    tenant_id = _require_tenant(payload)
    _get_order_for_tenant(db, order_id=order_id, tenant_id=tenant_id)
    render = db.execute(
        select(LegalDocumentRender)
        .where(LegalDocumentRender.order_id == order_id)
        .order_by(LegalDocumentRender.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    if render is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NO_RENDER", "message": "尚未生成文书；请先 POST 生成"},
        )
    return LegalDocumentRenderOut.model_validate(render)


@router.post(
    "/legal-conversion-orders/{order_id}/document",
    response_model=LegalDocumentRenderOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def render_doc(
    order_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalDocumentRenderOut:
    """生成 / 重新生成文书，每次创建新版本（version 递增）。"""
    tenant_id = _require_tenant(payload)
    order = _get_order_for_tenant(db, order_id=order_id, tenant_id=tenant_id)
    try:
        render = render_for_order(
            db,
            order=order,
            rendered_by=int(payload.get("user_id") or 0) or None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_NO_TEMPLATE", "message": str(exc)},
        ) from exc
    db.commit()
    db.refresh(render)
    return LegalDocumentRenderOut.model_validate(render)


@router.get(
    "/legal-conversion-orders/{order_id}/document/versions",
    response_model=list[LegalDocumentRenderOut],
)
async def list_doc_versions(
    order_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[LegalDocumentRenderOut]:
    tenant_id = _require_tenant(payload)
    _get_order_for_tenant(db, order_id=order_id, tenant_id=tenant_id)
    rows = (
        db.execute(
            select(LegalDocumentRender)
            .where(LegalDocumentRender.order_id == order_id)
            .order_by(LegalDocumentRender.version.desc())
        )
        .scalars()
        .all()
    )
    return [LegalDocumentRenderOut.model_validate(r) for r in rows]
