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
from sqlalchemy import or_ as sa_or_
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
    require_tenant_roles,
)
from app.models.call import CallRecord
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.models.work import WorkOrder
from app.schemas.common import PaginatedResponse
from app.schemas.work_order import (
    CallRef,
    CaseRef,
    WorkOrderCreate,
    WorkOrderDetailOut,
    WorkOrderFollowUpCreate,
    WorkOrderKpi,
    WorkOrderOut,
    WorkOrderPatch,
)
from app.services.audit import log_audit

router = APIRouter()

WORKORDER_ROLES = ("workorder", "coordinator", "admin", "supervisor")
# v1.9.8 — 协调员/督导/admin 只处理工单，不再允许创建；建工单必须从案件发起（agent）
# 工单必须关联案件（case_id 强制非空）
WORKORDER_CREATE_ROLES = ("agent", "admin")  # admin 保留兜底建单能力（运维）


def _require_tenant(payload: dict) -> int:
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    return tenant_id


def _wo_to_out(
    wo: WorkOrder,
    assignee_name: str | None,
    *,
    owner: OwnerProfile | None = None,
    case: CollectionCase | None = None,
    project: Project | None = None,
) -> WorkOrderOut:
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
        owner_name=owner.name if owner else None,
        owner_room=(f"{owner.building or ''}{owner.room or ''}" or None) if owner else None,
        project_id=case.project_id if case else None,
        project_name=project.name if project else None,
        amount_owed=str(case.amount_owed) if case and case.amount_owed is not None else None,
    )


def _resolve_assignee_name(db: Session, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    user = db.get(UserAccount, user_id)
    return user.name if user else None


@router.get("/kpi", response_model=WorkOrderKpi)
def get_work_orders_kpi(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*WORKORDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> WorkOrderKpi:
    """v1.9.6 — 协调员工作台顶部 4 张 KPI 卡。"""
    from datetime import UTC

    tenant_id = _require_tenant(payload)
    now = datetime.now(UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)

    open_count = (
        db.execute(
            select(func.count(WorkOrder.id))
            .where(WorkOrder.tenant_id == tenant_id)
            .where(WorkOrder.status == "open")
        ).scalar_one()
        or 0
    )

    in_progress_count = (
        db.execute(
            select(func.count(WorkOrder.id))
            .where(WorkOrder.tenant_id == tenant_id)
            .where(WorkOrder.status == "in_progress")
        ).scalar_one()
        or 0
    )

    closed_statuses = ("resolved", "closed")
    closed_this_month = (
        db.execute(
            select(func.count(WorkOrder.id))
            .where(WorkOrder.tenant_id == tenant_id)
            .where(WorkOrder.status.in_(closed_statuses))
            .where(WorkOrder.updated_at >= month_start)
        ).scalar_one()
        or 0
    )

    avg_seconds = db.execute(
        select(func.avg(func.extract("epoch", WorkOrder.updated_at - WorkOrder.created_at)))
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
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*WORKORDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None, max_length=100),
    status: str | None = Query(None, max_length=50),
    order_type: str | None = Query(None, max_length=50),
    priority: str | None = Query(None, max_length=20),
    project_id: int | None = Query(None, description="按所属项目过滤"),
    since: datetime | None = Query(None, description="filter created_at >= since"),
    until: datetime | None = Query(None, description="filter created_at < until"),
    room: str | None = Query(None, max_length=20, description="filter by owner.room"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[WorkOrderOut]:
    tenant_id = _require_tenant(payload)

    # v1.9.7 — 始终 join case + owner + project，使得列表可返回业主/房号/项目/欠费上下文
    stmt = (
        select(WorkOrder, OwnerProfile, CollectionCase, Project)
        .outerjoin(CollectionCase, CollectionCase.id == WorkOrder.case_id)
        .outerjoin(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .outerjoin(Project, Project.id == CollectionCase.project_id)
        .where(WorkOrder.tenant_id == tenant_id)
    )
    if status:
        stmt = stmt.where(WorkOrder.status == status)
    if order_type:
        stmt = stmt.where(WorkOrder.order_type == order_type)
    if priority:
        stmt = stmt.where(WorkOrder.priority == priority)
    if project_id is not None:
        stmt = stmt.where(CollectionCase.project_id == project_id)
    if q:
        # v1.9.7 — q 扩展到业主姓名/房号
        stmt = stmt.where(
            sa_or_(
                WorkOrder.description.ilike(f"%{q}%"),
                OwnerProfile.name.ilike(f"%{q}%"),
                OwnerProfile.room.ilike(f"%{q}%"),
            )
        )
    if since:
        stmt = stmt.where(WorkOrder.created_at >= since)
    if until:
        stmt = stmt.where(WorkOrder.created_at < until)
    if room:
        stmt = stmt.where(OwnerProfile.room == room)

    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    rows = db.execute(
        stmt.order_by(WorkOrder.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = [
        _wo_to_out(
            wo,
            _resolve_assignee_name(db, wo.assigned_to),
            owner=owner,
            case=case,
            project=project,
        )
        for wo, owner, case, project in rows
    ]
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

    # v1.9.8 — 工单必须关联案件（不允许独立工单）
    if body.case_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_CASE_REQUIRED", "message": "工单必须关联案件"},
        )
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
                )
                .limit(1)
            ).scalar_one_or_none()

        if project_coord_id is not None:
            assigned_to = project_coord_id
            auto_assigned = True
        else:
            coordinator_ids = list(
                db.execute(
                    select(UserTenantMembership.user_id)
                    .where(
                        UserTenantMembership.tenant_id == tenant_id,
                        UserTenantMembership.role.in_(["coordinator", "workorder"]),
                        UserTenantMembership.is_active.is_(True),
                    )
                    .order_by(UserTenantMembership.id)
                )
                .scalars()
                .all()
            )
            if coordinator_ids:
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                counts: dict[int, int] = dict(
                    db.execute(
                        select(WorkOrder.assigned_to, func.count())
                        .where(
                            WorkOrder.tenant_id == tenant_id,
                            WorkOrder.assigned_to.in_(coordinator_ids),
                            WorkOrder.created_at >= today_start,
                        )
                        .group_by(WorkOrder.assigned_to)
                    ).all()
                )
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
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*WORKORDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> WorkOrderDetailOut:
    from app.models.work_order_follow_up import WorkOrderFollowUp

    tenant_id = _require_tenant(payload)

    wo = db.get(WorkOrder, order_id)
    if wo is None or wo.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "工单不存在"},
        )

    owner: OwnerProfile | None = None
    case: CollectionCase | None = None
    project: Project | None = None
    if wo.case_id is not None:
        case = db.get(CollectionCase, wo.case_id)
        if case is not None:
            owner = db.get(OwnerProfile, case.owner_id)
            if case.project_id:
                project = db.get(Project, case.project_id)

    base = _wo_to_out(
        wo,
        _resolve_assignee_name(db, wo.assigned_to),
        owner=owner,
        case=case,
        project=project,
    )

    case_ref: CaseRef | None = None
    if case is not None and owner is not None:
        case_ref = CaseRef(
            id=case.id,
            stage=case.stage,
            owner_name=owner.name,
            owner_phone_masked=display_owner_phone(
                owner.phone_enc,
                reveal=should_reveal_owner_phone(
                    role=payload.get("role", ""),
                    provider_id=payload.get("provider_id"),
                    contract_active=is_provider_contract_active(
                        db, tenant_id, payload.get("provider_id")
                    ),
                ),
            )
            or "",
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

    # v1.9.7 — follow-ups（按时间升序）
    follow_rows = (
        db.execute(
            select(WorkOrderFollowUp)
            .where(WorkOrderFollowUp.work_order_id == order_id)
            .where(WorkOrderFollowUp.tenant_id == tenant_id)
            .order_by(WorkOrderFollowUp.occurred_at.asc())
        )
        .scalars()
        .all()
    )
    actor_ids = {f.actor_user_id for f in follow_rows if f.actor_user_id}
    actor_map = (
        dict(
            db.execute(
                select(UserAccount.id, UserAccount.name).where(UserAccount.id.in_(actor_ids))
            ).all()
        )
        if actor_ids
        else {}
    )
    follow_ups = [
        {
            "id": f.id,
            "work_order_id": f.work_order_id,
            "case_id": f.case_id,
            "actor_user_id": f.actor_user_id,
            "actor_name": actor_map.get(f.actor_user_id),
            "occurred_at": f.occurred_at,
            "kind": f.kind,
            "note": f.note,
        }
        for f in follow_rows
    ]

    return WorkOrderDetailOut(
        **base.model_dump(),
        case=case_ref,
        call=call_ref,
        follow_ups=follow_ups,  # type: ignore[arg-type]
    )


@router.post(
    "/{order_id}/follow-ups",
    response_model=WorkOrderDetailOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def add_follow_up(
    order_id: int,
    body: WorkOrderFollowUpCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*WORKORDER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> WorkOrderDetailOut:
    """v1.9.7 — 协调员/admin 给工单加跟进记录。"""
    from datetime import UTC

    from app.models.work_order_follow_up import WorkOrderFollowUp

    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)

    wo = db.get(WorkOrder, order_id)
    if wo is None or wo.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "工单不存在"},
        )

    follow = WorkOrderFollowUp(
        tenant_id=tenant_id,
        work_order_id=order_id,
        case_id=wo.case_id,
        actor_user_id=user_id,
        occurred_at=datetime.now(UTC),
        kind=body.kind,
        note=body.note,
    )
    db.add(follow)
    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=payload.get("role"),
        tenant_id=tenant_id,
        action="workorder.follow_up_added",
        target_type="work_order",
        target_id=order_id,
        payload={"kind": body.kind},
    )
    db.commit()

    return await get_work_order(order_id, payload, _user, db)


@router.patch("/{order_id}", response_model=WorkOrderOut)
async def patch_work_order(
    order_id: int,
    body: WorkOrderPatch,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*WORKORDER_ROLES))],
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
    if wo.status == "completed" and prev_status != "completed":
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
