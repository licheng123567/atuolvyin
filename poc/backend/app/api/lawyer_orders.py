"""v1.5.7 S2 — 律师工作台 API (PRD §20.4)。

GET    /api/v1/lawyer/orders                          列出派给当前律师的订单
GET    /api/v1/lawyer/orders/{id}                     订单详情
POST   /api/v1/lawyer/orders/{id}/upload-document     律师上传文书 (mock：仅记录元数据)
POST   /api/v1/lawyer/orders/{id}/complete            律师标记完成 → completed + 触发分账
GET    /api/v1/lawyer/me                              当前律师 + 律所基本信息

身份解析：登录用户经 require_roles('legal') 后，从 law_firm_membership 表查 role_in_firm='lawyer'
的活跃记录决定本人是哪位律师。
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
from app.models.legal_document import LegalDocument
from app.services.legal_order_enrich import enrich_order

router = APIRouter()

LEGAL_ROLES = ("legal",)


def _resolve_lawyer(db: Session, user_id: int) -> tuple[LawFirmMembership, LawFirmLawyer]:
    membership = (
        db.execute(
            select(LawFirmMembership)
            .where(LawFirmMembership.user_id == user_id)
            .where(LawFirmMembership.role_in_firm == "lawyer")
            .where(LawFirmMembership.is_active.is_(True))
            .order_by(LawFirmMembership.id)
        )
        .scalars()
        .first()
    )
    if not membership or not membership.lawyer_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ERR_NOT_LAWYER",
                "message": "当前用户未注册为任何律师",
            },
        )
    lawyer = db.get(LawFirmLawyer, membership.lawyer_id)
    if not lawyer:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_LAWYER_NOT_FOUND", "message": "关联律师档案不存在"},
        )
    return membership, lawyer


@router.get("/orders")
async def list_my_orders(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    status: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict:
    user_id = int(payload["user_id"])
    _, lawyer = _resolve_lawyer(db, user_id)
    stmt = (
        select(LegalConversionOrder)
        .where(LegalConversionOrder.lawyer_id == lawyer.id)
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
async def get_my_order(
    order_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    user_id = int(payload["user_id"])
    _, lawyer = _resolve_lawyer(db, user_id)
    order = db.get(LegalConversionOrder, order_id)
    if not order or order.lawyer_id != lawyer.id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "订单不存在或未指派给当前律师"},
        )
    return enrich_order(db, order)


@router.post("/orders/{order_id}/upload-document")
async def upload_document(
    order_id: int,
    body: dict,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """body = {"doc_type": str, "filename": str, "object_key": str}

    mock：仅记录元数据，实际文件上传走 MinIO 签名 URL，前端单独走流。
    """
    doc_type = body.get("doc_type")
    filename = body.get("filename")
    object_key = body.get("object_key", f"mock/{order_id}/{filename}")
    if not isinstance(doc_type, str) or not isinstance(filename, str):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_VALIDATION", "message": "doc_type 和 filename 必填"},
        )
    user_id = int(payload["user_id"])
    _, lawyer = _resolve_lawyer(db, user_id)
    order = db.get(LegalConversionOrder, order_id)
    if not order or order.lawyer_id != lawyer.id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "订单不存在或未指派给当前律师"},
        )
    if order.status not in {"in_service", "completed"}:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATE",
                "message": f"订单当前状态为 {order.status}，不可上传文书",
            },
        )
    doc = LegalDocument(
        case_id=order.case_id,
        doc_type=doc_type,
        filename=filename,
        object_key=object_key,
        uploaded_by=user_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {
        "id": doc.id,
        "doc_type": doc.doc_type,
        "filename": doc.filename,
        "object_key": doc.object_key,
        "uploaded_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.post("/orders/{order_id}/complete")
async def complete_my_order(
    order_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    user_id = int(payload["user_id"])
    _, lawyer = _resolve_lawyer(db, user_id)
    order = db.get(LegalConversionOrder, order_id)
    if not order or order.lawyer_id != lawyer.id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "订单不存在或未指派给当前律师"},
        )
    if order.status != "in_service":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATE",
                "message": f"订单当前状态为 {order.status}，仅 in_service 可完结",
            },
        )
    order.status = "completed"
    order.completed_at = datetime.now(UTC)
    db.add(order)
    # mock：分账记录由独立 job 触发；本端点仅打标
    db.commit()
    db.refresh(order)
    return enrich_order(db, order)


@router.get("/me", response_model=dict)
async def get_lawyer_context(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    user_id = int(payload["user_id"])
    membership, lawyer = _resolve_lawyer(db, user_id)
    firm = db.get(LawFirm, membership.law_firm_id)
    return {
        "lawyer_id": lawyer.id,
        "lawyer_name": lawyer.name,
        "specialties": lawyer.specialties or [],
        "law_firm_id": firm.id if firm else None,
        "law_firm_name": firm.name if firm else None,
    }
