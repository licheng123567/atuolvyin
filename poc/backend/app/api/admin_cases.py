from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone
from app.core.db import get_db
from app.core.security import (
    get_token_payload,
    mask_phone,
    require_roles,
)
from app.models.call import AnalysisResult, CallRecord, Transcript
from app.models.case import CollectionCase, OwnerProfile
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.services.case_timeline import build_case_timeline
from app.schemas.case import (
    CaseAssignRequest,
    CaseAssignResponse,
    CaseCallItem,
    CaseDetailResponse,
    CaseImportRequest,
    CaseImportResponse,
    CaseResponse,
    CaseStageUpdate,
    CaseWithOwnerResponse,
    OwnerInfo,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()

ADMIN_ROLES = ("admin",)


def _require_tenant(payload: dict) -> int:
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    return tenant_id


def _calc_priority(
    amount_owed: Decimal | None, months_overdue: int | None
) -> int:
    return int(float(amount_owed or 0) * 0.4 + float(months_overdue or 0) * 0.3)


def _case_row_to_response(
    case: CollectionCase, owner: OwnerProfile
) -> CaseWithOwnerResponse:
    return CaseWithOwnerResponse(
        id=case.id,
        tenant_id=case.tenant_id,
        project_id=case.project_id,
        owner=OwnerInfo(
            id=owner.id,
            name=owner.name,
            phone_masked=mask_phone(owner.phone_enc),
            building=owner.building,
            room=owner.room,
            do_not_call=owner.do_not_call,
        ),
        assigned_to=case.assigned_to,
        pool_type=case.pool_type,
        stage=case.stage,
        amount_owed=case.amount_owed,
        months_overdue=case.months_overdue,
        priority_score=case.priority_score,
        last_contact_at=case.last_contact_at,
        monthly_contact_count=case.monthly_contact_count,
        status=case.status,
        notes=case.notes,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.post("/cases/import", response_model=CaseImportResponse, status_code=201)
async def import_cases(
    body: CaseImportRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseImportResponse:
    tenant_id = _require_tenant(payload)

    # 校验 project_id 属本租户
    if body.project_id is not None:
        from app.models.case import Project
        project = db.execute(
            select(Project).where(
                Project.id == body.project_id,
                Project.tenant_id == tenant_id,
            )
        ).scalar_one_or_none()
        if project is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"code": "ERR_INVALID_PROJECT", "message": "项目不存在或不属本租户"},
            )

    imported = 0
    for row in body.rows:
        existing_owner = db.execute(
            select(OwnerProfile).where(
                OwnerProfile.tenant_id == tenant_id,
                OwnerProfile.phone_enc == encrypt_phone(row.phone),
            )
        ).scalar_one_or_none()

        if existing_owner is None:
            owner = OwnerProfile(
                tenant_id=tenant_id,
                name=row.name,
                phone_enc=encrypt_phone(row.phone),
                building=row.building,
                room=row.room,
            )
            db.add(owner)
            db.flush()
        else:
            owner = existing_owner

        case = CollectionCase(
            tenant_id=tenant_id,
            project_id=body.project_id,
            owner_id=owner.id,
            pool_type="public",
            stage="new",
            amount_owed=row.amount_owed,
            months_overdue=row.months_overdue,
            priority_score=_calc_priority(row.amount_owed, row.months_overdue),
            notes=row.notes,
        )
        db.add(case)
        imported += 1

    db.flush()
    db.commit()
    return CaseImportResponse(imported=imported, skipped=0, errors=[])


@router.get("/cases", response_model=PaginatedResponse[CaseWithOwnerResponse])
async def list_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    stage: str | None = Query(None),
    pool_type: str | None = Query(None),
    assigned_to: int | None = Query(None),
    project_id: int | None = Query(None),
    building: str | None = Query(None),
    keyword: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CaseWithOwnerResponse]:
    tenant_id = _require_tenant(payload)

    stmt = (
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(CollectionCase.tenant_id == tenant_id)
    )
    if stage:
        stmt = stmt.where(CollectionCase.stage == stage)
    if pool_type:
        stmt = stmt.where(CollectionCase.pool_type == pool_type)
    if assigned_to:
        stmt = stmt.where(CollectionCase.assigned_to == assigned_to)
    if project_id is not None:
        stmt = stmt.where(CollectionCase.project_id == project_id)
    if building:
        stmt = stmt.where(OwnerProfile.building == building)
    if keyword:
        stmt = stmt.where(OwnerProfile.name.ilike(f"%{keyword}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    rows = db.execute(
        stmt.order_by(CollectionCase.priority_score.desc(), CollectionCase.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[_case_row_to_response(case, owner) for case, owner in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/cases/buildings")
async def list_distinct_buildings(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    project_id: int | None = Query(None),
) -> list[str]:
    """返回本租户去重后的楼栋列表，按 project_id 过滤。"""
    tenant_id = _require_tenant(payload)
    stmt = (
        select(OwnerProfile.building)
        .join(CollectionCase, CollectionCase.owner_id == OwnerProfile.id)
        .where(
            CollectionCase.tenant_id == tenant_id,
            OwnerProfile.building.isnot(None),
        )
        .distinct()
    )
    if project_id is not None:
        stmt = stmt.where(CollectionCase.project_id == project_id)
    rows = db.execute(stmt.order_by(OwnerProfile.building)).scalars().all()
    return [b for b in rows if b]


@router.post("/cases/assign", response_model=CaseAssignResponse)
async def assign_cases(
    body: CaseAssignRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseAssignResponse:
    tenant_id = _require_tenant(payload)

    member = db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == body.assign_to,
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_USER_NOT_IN_TENANT", "message": "指定用户不在本租户"},
        )

    stmt = (
        update(CollectionCase)
        .where(
            CollectionCase.id.in_(body.case_ids),
            CollectionCase.tenant_id == tenant_id,
        )
        .values(assigned_to=body.assign_to, pool_type="private")
    )
    result = db.execute(stmt)
    db.commit()
    return CaseAssignResponse(updated_count=result.rowcount)


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
async def get_case(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseDetailResponse:
    tenant_id = _require_tenant(payload)
    row = db.execute(
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(
            CollectionCase.id == case_id,
            CollectionCase.tenant_id == tenant_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    case, owner = row[0], row[1]

    # Build call timeline
    call_rows = db.execute(
        select(CallRecord, UserAccount.name.label("agent_name"))
        .join(UserAccount, UserAccount.id == CallRecord.caller_user_id)
        .where(
            CallRecord.case_id == case_id,
            CallRecord.tenant_id == tenant_id,
        )
        .order_by(CallRecord.started_at.desc().nulls_last())
    ).all()

    call_items: list[CaseCallItem] = []
    for call_row in call_rows:
        call = call_row[0]
        agent_name = call_row[1]

        analysis = db.execute(
            select(AnalysisResult).where(AnalysisResult.call_id == call.id)
        ).scalar_one_or_none()
        transcript = db.execute(
            select(Transcript).where(Transcript.call_id == call.id)
        ).scalar_one_or_none()

        confidence = None
        if analysis and analysis.key_segments:
            confidence = analysis.key_segments.get("confidence")

        preview = None
        if transcript and transcript.full_text:
            preview = transcript.full_text[:100]

        call_items.append(CaseCallItem(
            id=call.id,
            started_at=call.started_at,
            duration_sec=call.duration_sec,
            status=call.status,
            transcript_preview=preview,
            result_tag=call.result_tag,
            confidence=confidence,
            agent_name=agent_name,
        ))

    return CaseDetailResponse(
        id=case.id,
        tenant_id=case.tenant_id,
        project_id=case.project_id,
        owner=OwnerInfo(
            id=owner.id,
            name=owner.name,
            phone_masked=mask_phone(owner.phone_enc),
            building=owner.building,
            room=owner.room,
            do_not_call=owner.do_not_call,
        ),
        assigned_to=case.assigned_to,
        pool_type=case.pool_type,
        stage=case.stage,
        amount_owed=case.amount_owed,
        months_overdue=case.months_overdue,
        priority_score=case.priority_score,
        last_contact_at=case.last_contact_at,
        monthly_contact_count=case.monthly_contact_count,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        calls=call_items,
        timeline_events=build_case_timeline(db, case_id, tenant_id),
    )


@router.patch("/cases/{case_id}/stage", response_model=CaseResponse)
async def update_case_stage(
    case_id: int,
    body: CaseStageUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseResponse:
    tenant_id = _require_tenant(payload)
    case = db.get(CollectionCase, case_id)
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    prev_stage = case.stage
    case.stage = body.stage
    db.commit()
    db.refresh(case)
    # Sprint 15.4b — case_escalated 通知：进入 escalated/legal 阶段时触发
    _ESCALATED_STAGES = {"escalated", "legal", "litigation"}
    if (
        body.stage in _ESCALATED_STAGES
        and prev_stage not in _ESCALATED_STAGES
    ):
        from app.models.case import OwnerProfile
        from app.services.notifications.event_subscribers import notify_case_escalated
        owner = db.get(OwnerProfile, case.owner_id) if case.owner_id else None
        notify_case_escalated(
            db,
            tenant_id=int(case.tenant_id),
            case_id=int(case.id),
            owner_name=owner.name if owner else None,
            new_stage=body.stage,
            operator_user_id=int(payload.get("user_id") or 0) or None,
        )
        db.commit()
    return case
