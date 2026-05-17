"""§9.1 — 服务商法务职责边界。

服务商侧法务（role='legal' + provider_id 非空）专用端点。整路由用
require_provider_roles("legal") 守卫；案件归属经 CollectionCase.project_id →
Project.provider_id 推导。物业侧 legal 端点不受影响。
"""
from __future__ import annotations

from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.phone_visibility import display_owner_phone, should_reveal_owner_phone
from app.core.roles import ROLE_LEGAL
from app.core.security import get_token_payload, require_provider_roles
from app.models.call import CallRecord
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.provider_legal import (
    ProviderLegalCaseDetail,
    ProviderLegalCaseListItem,
)

router = APIRouter()


def _ctx(payload: dict) -> tuple[int, int, int]:
    """返回 (tenant_id, provider_id, user_id)。require_provider_roles 已保证 provider_id 非空。"""
    tenant_id = int(payload.get("tenant_id") or 0)
    provider_id = payload.get("provider_id")
    user_id = int(payload.get("user_id") or 0)
    if not tenant_id or provider_id is None or not user_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "缺少必要的租户/服务商上下文"},
        )
    return tenant_id, int(provider_id), user_id


def _provider_legal_case_filter(tenant_id: int, provider_id: int):
    """案件可见性子句：本服务商 tenant 内 active 且服务期内项目下的案件。"""
    return sa.and_(
        CollectionCase.tenant_id == tenant_id,
        CollectionCase.project_id.in_(
            select(Project.id).where(
                Project.tenant_id == tenant_id,
                Project.provider_id == provider_id,
                Project.status == "active",
                sa.or_(Project.plan_end.is_(None), Project.plan_end >= func.now()),
            )
        ),
    )


def _owner_phone_reveal(provider_id: int) -> bool:
    """服务商法务整理转化前的普通案件 —— 无 LegalCase.stage → 脱敏。"""
    return should_reveal_owner_phone(
        role=ROLE_LEGAL, provider_id=provider_id, legal_case_stage=None
    )


@router.get("/cases", response_model=PaginatedResponse[ProviderLegalCaseListItem])
def list_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(ROLE_LEGAL))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ProviderLegalCaseListItem]:
    tenant_id, provider_id, _ = _ctx(payload)
    case_filter = _provider_legal_case_filter(tenant_id, provider_id)
    total = int(db.execute(select(func.count(CollectionCase.id)).where(case_filter)).scalar_one())
    rows = db.execute(
        select(CollectionCase, OwnerProfile, Project.name.label("project_name"))
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .outerjoin(Project, Project.id == CollectionCase.project_id)
        .where(case_filter)
        .order_by(desc(CollectionCase.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    reveal = _owner_phone_reveal(provider_id)
    items = [
        ProviderLegalCaseListItem(
            case_id=c.id,
            owner_name=o.name,
            owner_phone_masked=display_owner_phone(o.phone_enc, reveal=reveal),
            building=o.building,
            room=o.room,
            project_id=c.project_id,
            project_name=pn,
            amount_owed=c.amount_owed,
            months_overdue=c.months_overdue,
            stage=c.stage,
        )
        for c, o, pn in rows
    ]
    return PaginatedResponse[ProviderLegalCaseListItem](
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/cases/{case_id}", response_model=ProviderLegalCaseDetail)
def get_case(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(ROLE_LEGAL))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderLegalCaseDetail:
    tenant_id, provider_id, _ = _ctx(payload)
    row = db.execute(
        select(CollectionCase, OwnerProfile, Project.name.label("project_name"))
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .outerjoin(Project, Project.id == CollectionCase.project_id)
        .where(
            CollectionCase.id == case_id,
            _provider_legal_case_filter(tenant_id, provider_id),
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    case, owner, project_name = row
    call_count = int(
        db.execute(
            select(func.count(CallRecord.id)).where(CallRecord.case_id == case_id)
        ).scalar_one()
    )
    last_call_at = db.execute(
        select(func.max(CallRecord.started_at)).where(CallRecord.case_id == case_id)
    ).scalar_one_or_none()
    reveal = _owner_phone_reveal(provider_id)
    return ProviderLegalCaseDetail(
        case_id=case.id,
        owner_name=owner.name,
        owner_phone_masked=display_owner_phone(owner.phone_enc, reveal=reveal),
        building=owner.building,
        room=owner.room,
        project_id=case.project_id,
        project_name=project_name,
        pool_type=case.pool_type,
        stage=case.stage,
        status=case.status,
        amount_owed=case.amount_owed,
        principal_amount=case.principal_amount,
        late_fee_amount=case.late_fee_amount,
        months_overdue=case.months_overdue,
        arrears_reason=case.arrears_reason,
        last_contact_at=case.last_contact_at,
        monthly_contact_count=case.monthly_contact_count,
        priority_score=case.priority_score,
        call_count=call_count,
        last_call_at=last_call_at,
    )
