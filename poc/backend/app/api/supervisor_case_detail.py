"""v1.5.7 S3 — 督导侧案件详情 API。

GET /api/v1/supervisor/cases/{case_id}

v1.6.9 — 改为复用 admin/agent 同款 build_case_detail_response，返回标准
CaseDetailResponse；督导/admin/legal 三个角色看相同字段。前端用同款共享组件。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.case import CollectionCase, OwnerProfile
from app.schemas.case import CaseDetailResponse

from .admin_cases import build_case_detail_response

router = APIRouter()

SUPERVISOR_ROLES = ("supervisor", "admin", "legal")
# v1.6 — legal 角色（物业法务对接人）可只读案件全貌（限本租户）；律所/律师不在内


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
async def get_case_detail(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseDetailResponse:
    tenant_id = payload.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "当前角色未关联租户"},
        )
    tenant_id = int(tenant_id)
    case = db.get(CollectionCase, case_id)
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不属于本租户"},
        )
    owner = db.get(OwnerProfile, case.owner_id) if case.owner_id else None
    if owner is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NO_OWNER", "message": "案件无业主信息"},
        )
    # v1.7.0 — supervisor 是物业内部角色，phone_masked 字段会返回明文
    return build_case_detail_response(
        db, case, owner, tenant_id=tenant_id, include_phone_plain=False,
        viewer_role=payload.get("role"),
        viewer_provider_id=payload.get("provider_id"),
    )
