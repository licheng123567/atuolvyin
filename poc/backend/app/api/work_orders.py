"""Sprint 13 — Work Order management for `workorder` role.

GET    /api/v1/workorders                     list w/ q + status + order_type filters
POST   /api/v1/workorders                     create
GET    /api/v1/workorders/{id}                detail incl. case/call refs
PATCH  /api/v1/workorders/{id}                partial update
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import (
    get_token_payload,
    mask_phone,
    require_roles,
)
from app.models.call import CallRecord
from app.models.case import CollectionCase, OwnerProfile
from app.models.user import UserAccount
from app.models.work import WorkOrder
from app.schemas.common import PaginatedResponse
from app.schemas.work_order import (
    CallRef,
    CaseRef,
    WorkOrderCreate,
    WorkOrderDetailOut,
    WorkOrderOut,
    WorkOrderPatch,
)

router = APIRouter()

WORKORDER_ROLES = ("workorder", "admin", "supervisor")


def _require_tenant(payload: dict) -> int:
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    return tenant_id


def _wo_to_out(wo: WorkOrder, assignee_name: str | None) -> WorkOrderOut:
    return WorkOrderOut(
        id=wo.id,
        tenant_id=wo.tenant_id,
        case_id=wo.case_id,
        call_id=wo.call_id,
        order_type=wo.order_type,
        description=wo.description,
        assigned_to=wo.assigned_to,
        status=wo.status,
        resolution=wo.resolution,
        created_at=wo.created_at,
        updated_at=wo.updated_at,
        assignee_name=assignee_name,
    )


def _resolve_assignee_name(db: Session, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    user = db.get(UserAccount, user_id)
    return user.name if user else None


@router.get("", response_model=PaginatedResponse[WorkOrderOut])
async def list_work_orders(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*WORKORDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None, max_length=100),
    status: str | None = Query(None, max_length=50),
    order_type: str | None = Query(None, max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[WorkOrderOut]:
    tenant_id = _require_tenant(payload)

    stmt = select(WorkOrder).where(WorkOrder.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(WorkOrder.status == status)
    if order_type:
        stmt = stmt.where(WorkOrder.order_type == order_type)
    if q:
        stmt = stmt.where(WorkOrder.description.ilike(f"%{q}%"))

    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    rows = (
        db.execute(
            stmt.order_by(WorkOrder.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        .scalars()
        .all()
    )

    items = [_wo_to_out(wo, _resolve_assignee_name(db, wo.assigned_to)) for wo in rows]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=WorkOrderOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_work_order(
    body: WorkOrderCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*WORKORDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> WorkOrderOut:
    tenant_id = _require_tenant(payload)

    if body.case_id is not None:
        cc = db.get(CollectionCase, body.case_id)
        if cc is None or cc.tenant_id != tenant_id:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail={"code": "ERR_CASE_NOT_FOUND", "message": "案件不存在"},
            )
    if body.call_id is not None:
        call = db.get(CallRecord, body.call_id)
        if call is None or call.tenant_id != tenant_id:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail={"code": "ERR_CALL_NOT_FOUND", "message": "通话记录不存在"},
            )

    wo = WorkOrder(
        tenant_id=tenant_id,
        case_id=body.case_id,
        call_id=body.call_id,
        order_type=body.order_type,
        description=body.description,
        assigned_to=body.assigned_to,
        status="open",
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)

    return _wo_to_out(wo, _resolve_assignee_name(db, wo.assigned_to))


@router.get("/{order_id}", response_model=WorkOrderDetailOut)
async def get_work_order(
    order_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*WORKORDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> WorkOrderDetailOut:
    tenant_id = _require_tenant(payload)

    wo = db.get(WorkOrder, order_id)
    if wo is None or wo.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "工单不存在"},
        )

    base = _wo_to_out(wo, _resolve_assignee_name(db, wo.assigned_to))

    case_ref: CaseRef | None = None
    if wo.case_id is not None:
        row = db.execute(
            select(CollectionCase, OwnerProfile)
            .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
            .where(CollectionCase.id == wo.case_id)
        ).one_or_none()
        if row is not None:
            cc, owner = row[0], row[1]
            case_ref = CaseRef(
                id=cc.id,
                stage=cc.stage,
                owner_name=owner.name,
                owner_phone_masked=mask_phone(owner.phone_enc),
            )

    call_ref: CallRef | None = None
    if wo.call_id is not None:
        call = db.get(CallRecord, wo.call_id)
        if call is not None:
            call_ref = CallRef(
                id=call.id,
                started_at=call.started_at,
                duration_sec=call.duration_sec,
                result_tag=call.result_tag,
            )

    return WorkOrderDetailOut(
        **base.model_dump(),
        case=case_ref,
        call=call_ref,
    )


@router.patch("/{order_id}", response_model=WorkOrderOut)
async def patch_work_order(
    order_id: int,
    body: WorkOrderPatch,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*WORKORDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> WorkOrderOut:
    tenant_id = _require_tenant(payload)

    wo = db.get(WorkOrder, order_id)
    if wo is None or wo.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "工单不存在"},
        )

    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(wo, field, value)

    db.commit()
    db.refresh(wo)
    return _wo_to_out(wo, _resolve_assignee_name(db, wo.assigned_to))
