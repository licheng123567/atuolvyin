from __future__ import annotations

from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from datetime import UTC, datetime

from pydantic import BaseModel

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
)
from app.schemas.common import PaginatedResponse
from app.services.audit import log_audit
from app.services.case_timeline import build_case_timeline

from app.models.case import Project
from app.models.tenant import UserTenantMembership

from .admin_cases import _case_row_to_response, _require_tenant


def _agent_provider_id(db: Session, user_id: int, tenant_id: int) -> int | None:
    """Return the provider_id for an agent_external; None for agent_internal."""
    m = db.execute(
        sa.select(UserTenantMembership).where(
            UserTenantMembership.user_id == user_id,
            UserTenantMembership.tenant_id == tenant_id,
        )
    ).scalars().first()
    return m.provider_id if m and m.provider_id else None


def _build_visible_case_filter(
    db: Session, user_id: int, tenant_id: int, role: str
):
    """Build SQLAlchemy WHERE clause for cases visible to the agent.

    内勤：私海（自己的）+ 公海（无项目 OR 项目无服务商 OR 项目允许协助）
    外勤：私海（自己的）+ 公海（项目 provider_id == 我的 provider_id）
    """
    own_clause = CollectionCase.assigned_to == user_id

    if role == "agent_external":
        provider_id = _agent_provider_id(db, user_id, tenant_id)
        if provider_id is None:
            return own_clause
        # 外勤可见：自己的 OR 公海+本服务商负责的项目
        external_visible = sa.and_(
            CollectionCase.pool_type == "public",
            CollectionCase.assigned_to.is_(None),
            CollectionCase.project_id.in_(
                sa.select(Project.id).where(
                    Project.tenant_id == tenant_id,
                    Project.provider_id == provider_id,
                )
            ),
        )
        return sa.or_(own_clause, external_visible)

    # 内勤：自己的 + 公海（无项目 OR 项目无服务商 OR 项目开了协助开关）
    visible_project_ids = sa.select(Project.id).where(
        Project.tenant_id == tenant_id,
        sa.or_(
            Project.provider_id.is_(None),
            Project.allow_internal_assist.is_(True),
        ),
    )
    internal_visible = sa.and_(
        CollectionCase.pool_type == "public",
        CollectionCase.assigned_to.is_(None),
        sa.or_(
            CollectionCase.project_id.is_(None),
            CollectionCase.project_id.in_(visible_project_ids),
        ),
    )
    return sa.or_(own_clause, internal_visible)

router = APIRouter()

AGENT_ROLES = ("agent_internal", "agent_external")


@router.get("/cases", response_model=PaginatedResponse[CaseWithOwnerResponse])
async def list_my_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    pool_type: str | None = Query(None),
    stage: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CaseWithOwnerResponse]:
    tenant_id = _require_tenant(payload)
    role = payload.get("role", "")

    # v1.4 — 按 agent 角色 + 项目 provider_id + allow_internal_assist 过滤
    visible_clause = _build_visible_case_filter(db, user.id, tenant_id, role)
    stmt = (
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(
            CollectionCase.tenant_id == tenant_id,
            visible_clause,
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

    # v1.4 — 复用 list 同样的可见性规则（含项目+服务商+协助开关）
    visible_clause = _build_visible_case_filter(db, user.id, tenant_id, role)
    visible_case = db.execute(
        select(CollectionCase.id).where(
            CollectionCase.id == case_id,
            CollectionCase.tenant_id == tenant_id,
            visible_clause,
        )
    ).scalar_one_or_none()
    if visible_case is None:
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
        timeline_events=build_case_timeline(db, case_id, tenant_id),
    )


_CASE_INTENT_ACTIONS = {"transfer_supervisor", "transfer_legal"}


class _CaseIntentIn(BaseModel):
    action: str
    note: str | None = None


class _CaseIntentOut(BaseModel):
    case_id: int
    action: str
    recorded_at: datetime
    status: str  # "queued"


@router.post("/cases/{case_id}/intent", response_model=_CaseIntentOut, status_code=201)
def post_case_intent(
    case_id: int,
    body: _CaseIntentIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> _CaseIntentOut:
    """Sprint 16 — 坐席案件级意向 stub（转主管/转法务）。

    真实派发流程（v1.x 主管 inbox / 法务转化撮合）尚未上线；本端点产出 audit_log 痕迹。
    """
    if body.action not in _CASE_INTENT_ACTIONS:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_INVALID_INTENT", "message": "未知的意向动作"},
        )
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)
    role = str(payload.get("role") or "")

    case = db.get(CollectionCase, case_id)
    if case is None or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )

    now = datetime.now(UTC)
    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=tenant_id,
        action=f"case.intent.{body.action}",
        target_type="collection_case",
        target_id=case_id,
        payload={"note": body.note} if body.note else None,
    )
    db.commit()
    return _CaseIntentOut(case_id=case_id, action=body.action, recorded_at=now, status="queued")


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
