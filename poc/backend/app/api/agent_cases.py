from __future__ import annotations

from typing import Annotated, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_phone, mask_phone
from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.call import AnalysisResult, CallRecord, Transcript
from app.models.case import CollectionCase, OwnerProfile
from app.models.user import UserAccount
from app.schemas.case import (
    CaseCallItem,
    CaseDetailResponse,
    CaseResponse,
    CaseWithOwnerResponse,
    OwnerInfo,
    TimelineEvent,
)
from app.schemas.common import PaginatedResponse

from .admin_cases import _case_row_to_response, _require_tenant

router = APIRouter()

AGENT_ROLES = ("agent_internal", "agent_external")


@router.get("/cases", response_model=PaginatedResponse[CaseWithOwnerResponse])
async def list_my_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    pool_type: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CaseWithOwnerResponse]:
    tenant_id = _require_tenant(payload)

    # Agent sees: their own private cases OR unassigned public pool cases
    stmt = (
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(
            CollectionCase.tenant_id == tenant_id,
            sa.or_(
                CollectionCase.assigned_to == user.id,
                sa.and_(
                    CollectionCase.pool_type == "public",
                    CollectionCase.assigned_to.is_(None),
                ),
            ),
        )
    )
    if pool_type:
        stmt = stmt.where(CollectionCase.pool_type == pool_type)
    if stage:
        stmt = stmt.where(CollectionCase.stage == stage)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    rows = db.execute(
        stmt.order_by(
            CollectionCase.assigned_to.desc().nulls_last(),
            CollectionCase.priority_score.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[_case_row_to_response(case, owner) for case, owner in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
async def get_case_detail(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseDetailResponse:
    tenant_id = _require_tenant(payload)
    role: str = payload.get("role", "")

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

    # Agent can only see cases assigned to them OR public-pool cases not yet assigned
    if case.assigned_to != user.id and not (
        case.pool_type == "public" and case.assigned_to is None
    ):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "无权访问此案件"},
        )

    # Phone visibility by role
    phone_plain = decrypt_phone(owner.phone_enc) if role == "agent_internal" else None

    # Build call items
    call_rows = db.execute(
        select(CallRecord, UserAccount.name.label("agent_name"))
        .join(UserAccount, UserAccount.id == CallRecord.caller_user_id)
        .where(CallRecord.case_id == case_id, CallRecord.tenant_id == tenant_id)
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
        preview = transcript.full_text[:100] if transcript and transcript.full_text else None
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
            phone=phone_plain,
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
        timeline_events=[],
    )


@router.post("/cases/{case_id}/claim", response_model=CaseResponse)
async def claim_case(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseResponse:
    tenant_id = _require_tenant(payload)
    case = db.execute(
        select(CollectionCase)
        .where(CollectionCase.id == case_id)
        .with_for_update()
    ).scalar_one_or_none()
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    if case.pool_type != "public" or case.assigned_to is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_ALREADY_CLAIMED", "message": "案件已被认领或不在公池"},
        )
    case.pool_type = "private"
    case.assigned_to = user.id
    db.commit()
    db.refresh(case)
    return case
