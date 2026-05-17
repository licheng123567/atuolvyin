"""v1.6 — 物业法务对接人订单视图 API。

GET    /api/v1/legal/orders                 列出本租户所有法务转化订单（不论谁创建）
GET    /api/v1/legal/orders/{id}            订单详情

身份解析：登录用户 role=legal + tenant_id 来自 token。
区分物业法务（tenant_id ≠ NULL）和律所代表（tenant_id=NULL）：
  - 物业法务：看本租户全部订单（含 pending / dispatched / in_service / completed）
  - 律所代表：应改用 /api/v1/lawfirm/orders（按 LawFirmMembership 过滤）
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_tenant_roles
from app.models.legal_conversion import LegalConversionOrder
from app.services.legal_order_enrich import enrich_order

router = APIRouter()

LEGAL_ROLES = ("legal",)


@router.get("/orders")
def list_tenant_legal_orders(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    status: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict:
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ERR_NOT_TENANT_LEGAL",
                "message": "本接口仅供物业租户内法务对接人使用；律所代表请用 /api/v1/lawfirm/orders",
            },
        )
    stmt = (
        select(LegalConversionOrder)
        .where(LegalConversionOrder.tenant_id == int(tenant_id))
        .order_by(desc(LegalConversionOrder.id))
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
def get_tenant_legal_order(
    order_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_tenant_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "需要租户上下文"},
        )
    order = db.get(LegalConversionOrder, order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "订单不存在或不属于本租户"},
        )
    return enrich_order(db, order)
