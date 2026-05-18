"""v1.5.7 S3 — 督导侧案件详情 API。

GET /api/v1/supervisor/cases/{case_id}

v1.6.9 — 改为复用 admin/agent 同款 build_case_detail_response，返回标准
CaseDetailResponse；督导/admin/legal 三个角色看相同字段。前端用同款共享组件。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.case import CollectionCase, OwnerProfile
from app.models.legal_conversion import LegalConversionOrder
from app.schemas.case import CaseDetailResponse

from ._supervisor_scope import SupervisorScope, supervisor_case_filter, supervisor_scope
from .admin_cases import build_case_detail_response

router = APIRouter()

SUPERVISOR_ROLES = ("supervisor", "admin", "legal", "coordinator", "workorder")
# v1.6 — legal 角色（物业法务对接人）可只读案件全貌（限本租户）；律所/律师不在内
# v1.9.6 — coordinator / workorder（物业协调员）处理工单时需读案件全貌（业主画像 + 时间线）
# v1.6 — legal 角色（物业法务对接人）可只读案件全貌（限本租户）；律所/律师不在内


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
async def get_case_detail(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> CaseDetailResponse:
    case = db.execute(
        select(CollectionCase).where(
            CollectionCase.id == case_id,
            supervisor_case_filter(scope),
        )
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不在督导范围内"},
        )
    owner = db.get(OwnerProfile, case.owner_id) if case.owner_id else None
    if owner is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NO_OWNER", "message": "案件无业主信息"},
        )
    # v1.7.0 — supervisor 是物业内部角色，phone_masked 字段会返回明文
    # v1.9.4 — legal 角色处理本租户内部法务订单时（订单存在且非 cancelled/pending）
    #          直接给明文，便于打电话/发律师函
    role = payload.get("role")
    force_phone_reveal = False
    if role == "legal":
        legal_order_status = db.execute(
            select(LegalConversionOrder.status)
            .where(LegalConversionOrder.tenant_id == scope.tenant_id)
            .where(LegalConversionOrder.case_id == case_id)
            .order_by(LegalConversionOrder.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if legal_order_status in {
            "internal_processing",
            "closed_paid",
            "closed_promised",
            "closed_uncollectible",
            "escalated_to_lawfirm",
        }:
            force_phone_reveal = True

    return build_case_detail_response(
        db,
        case,
        owner,
        tenant_id=scope.tenant_id,
        include_phone_plain=False,
        viewer_role=role,
        viewer_provider_id=scope.provider_id,
        force_owner_phone_reveal=force_phone_reveal,
    )
