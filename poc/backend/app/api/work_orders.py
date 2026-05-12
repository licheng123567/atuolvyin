"""Sprint 13 — Work Order management for `workorder` role.

GET    /api/v1/workorders                     list w/ q + status + order_type filters
POST   /api/v1/workorders                     create
GET    /api/v1/workorders/{id}                detail incl. case/call refs
PATCH  /api/v1/workorders/{id}                partial update
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.phone_visibility import (
    display_owner_phone,
    is_provider_contract_active,
    should_reveal_owner_phone,
)
from app.core.security import (
    get_token_payload,
    require_roles,
)
from app.models.call import CallRecord
from app.models.case import CollectionCase, OwnerProfile
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.models.work import WorkOrder
from app.schemas.common import PaginatedResponse
from app.services.audit import log_audit
from app.schemas.work_order import (
    CallRef,
    CaseRef,
    WorkOrderCreate,
    WorkOrderDetailOut,
    WorkOrderKpi,
    WorkOrderOut,
    WorkOrderPatch,
)

router = APIRouter()

WORKORDER_ROLES = ("workorder", "coordinator", "admin", "supervisor")
# 创建工单允许坐席（PRD §10.1：通话现场起单），读取/分配等仍限管理角色
WORKORDER_CREATE_ROLES = WORKORDER_ROLES + ("agent_internal",)


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
        priority=wo.priority,
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


@router.get("/kpi", response_model=WorkOrderKpi)
def get_work_orders_kpi(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*WORKORDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> WorkOrderKpi:
    """v1.9.6 — 协调员工作台顶部 4 张 KPI 卡。"""
    from datetime import UTC

    tenant_id = _require_tenant(payload)
    now = datetime.now(UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)

    open_count = db.execute(
        select(func.count(WorkOrder.id))
        .where(WorkOrder.tenant_id == tenant_id)
        .where(WorkOrder.status == "open")
    ).scalar_one() or 0

    in_progress_count = db.execute(
        select(func.count(WorkOrder.id))
        .where(WorkOrder.tenant_id == tenant_id)
        .where(WorkOrder.status == "in_progress")
    ).scalar_one() or 0

    closed_statuses = ("resolved", "closed")
    closed_this_month = db.execute(
        select(func.count(WorkOrder.id))
        .where(WorkOrder.tenant_id == tenant_id)
        .where(WorkOrder.status.in_(closed_statuses))
        .where(WorkOrder.updated_at >= month_start)
    ).scalar_one() or 0

    avg_seconds = db.execute(
        select(
            func.avg(func.extract("epoch", WorkOrder.updated_at - WorkOrder.created_at))
        )
        .where(WorkOrder.tenant_id == tenant_id)
        .where(WorkOrder.status.in_(closed_statuses))
        .where(WorkOrder.updated_at >= month_start)
    ).scalar()
    avg_days = round(float(avg_seconds) / 86400.0, 1) if avg_seconds is not None else None

    return WorkOrderKpi(
        open_count=int(open_count),
        in_progress_count=int(in_progress_count),
        closed_this_month=int(closed_this_month),
        avg_processing_days=avg_days,
    )


@router.get("", response_model=PaginatedResponse[WorkOrderOut])
async def list_work_orders(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*WORKORDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None, max_length=100),
    status: str | None = Query(None, max_length=50),
    order_type: str | None = Query(None, max_length=50),
    priority: str | None = Query(None, max_length=20),
    since: datetime | None = Query(None, description="filter created_at >= since"),
    until: datetime | None = Query(None, description="filter created_at < until"),
    room: str | None = Query(None, max_length=20, description="filter by owner.room"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[WorkOrderOut]:
    tenant_id = _require_tenant(payload)

    stmt = select(WorkOrder).where(WorkOrder.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(WorkOrder.status == status)
    if order_type:
        stmt = stmt.where(WorkOrder.order_type == order_type)
    if priority:
        stmt = stmt.where(WorkOrder.priority == priority)
    if q:
        stmt = stmt.where(WorkOrder.description.ilike(f"%{q}%"))
    if since:
        stmt = stmt.where(WorkOrder.created_at >= since)
    if until:
        stmt = stmt.where(WorkOrder.created_at < until)
    if room:
        # Sprint 11.7 — filter by owner room via case join
        from app.models.case import CollectionCase, OwnerProfile

        stmt = (
            stmt.join(CollectionCase, CollectionCase.id == WorkOrder.case_id)
            .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
            .where(OwnerProfile.room == room)
        )

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
    _user: Annotated[UserAccount, Depends(require_roles(*WORKORDER_CREATE_ROLES))],
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

    # v1.5.6 — 未指定 assigned_to 时自动派单
    # 优先：case → project → 项目绑定的 coordinator（外包项目专属）
    # 兜底：本租户全部协调员 round-robin（按当日已派单数取最少）
    assigned_to = body.assigned_to
    auto_assigned = False
    if assigned_to is None:
        # 尝试：从 case 反查项目绑定的 coordinator
        project_coord_id: int | None = None
        if body.case_id is not None:
            from app.models.project_member import ProjectMember
            project_coord_id = db.execute(
                select(ProjectMember.user_id)
                .join(CollectionCase, CollectionCase.project_id == ProjectMember.project_id)
                .where(
                    CollectionCase.id == body.case_id,
                    ProjectMember.role_in_project == "coordinator",
                    ProjectMember.is_active.is_(True),
                ).limit(1)
            ).scalar_one_or_none()

        if project_coord_id is not None:
            assigned_to = project_coord_id
            auto_assigned = True
        else:
            coordinator_ids = list(db.execute(
                select(UserTenantMembership.user_id).where(
                    UserTenantMembership.tenant_id == tenant_id,
                    UserTenantMembership.role.in_(["coordinator", "workorder"]),
                    UserTenantMembership.is_active.is_(True),
                ).order_by(UserTenantMembership.id)
            ).scalars().all())
            if coordinator_ids:
                today_start = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                counts: dict[int, int] = dict(db.execute(
                    select(WorkOrder.assigned_to, func.count())
                    .where(
                        WorkOrder.tenant_id == tenant_id,
                        WorkOrder.assigned_to.in_(coordinator_ids),
                        WorkOrder.created_at >= today_start,
                    ).group_by(WorkOrder.assigned_to)
                ).all())
                assigned_to = min(coordinator_ids, key=lambda uid: counts.get(uid, 0))
                auto_assigned = True

    wo = WorkOrder(
        tenant_id=tenant_id,
        case_id=body.case_id,
        call_id=body.call_id,
        order_type=body.order_type,
        description=body.description,
        assigned_to=assigned_to,
        status="open",
        priority=body.priority,
    )
    db.add(wo)
    db.flush()

    if auto_assigned:
        log_audit(
            db,
            actor_user_id=int(payload.get("user_id") or 0) or None,
            actor_role=payload.get("role"),
            tenant_id=tenant_id,
            action="workorder.auto_assigned",
            target_type="work_order",
            target_id=wo.id,
            payload={"coordinator_id": assigned_to},
        )

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
                owner_phone_masked=display_owner_phone(
                    owner.phone_enc,
                    reveal=should_reveal_owner_phone(
                        role=payload.get("role", ""),
                        contract_active=is_provider_contract_active(
                            db, tenant_id, payload.get("provider_id")
                        ),
                    ),
                ) or "",
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
    prev_status = wo.status
    for field, value in data.items():
        setattr(wo, field, value)

    db.commit()
    db.refresh(wo)
    # Sprint 15.4b — work_order_completed 通知（open/in_progress → completed）
    if (
        wo.status == "completed"
        and prev_status != "completed"
    ):
        from app.services.notifications.event_subscribers import (
            notify_work_order_completed,
        )
        # 工单无 creator 字段，回落给 admin 角色 + 案件 assigned_to（如有）
        creator_uid: int | None = None
        if wo.case_id is not None:
            case = db.get(CollectionCase, wo.case_id)
            if case is not None:
                creator_uid = case.assigned_to
        notify_work_order_completed(
            db,
            tenant_id=int(wo.tenant_id),
            work_order_id=int(wo.id),
            title=wo.description[:80] if wo.description else f"工单#{wo.id}",
            creator_user_id=creator_uid,
            completer_user_id=int(payload.get("user_id") or 0) or None,
        )
        db.commit()
    return _wo_to_out(wo, _resolve_assignee_name(db, wo.assigned_to))
