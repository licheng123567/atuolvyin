"""v1.6.8 — 法务转化申请审批 API.

催收员通过 `POST /agent/cases/{id}/intent action=transfer_legal` 提交申请
（写入 LegalConversionRequest），督导/admin 在此 inbox 审批。

GET    /api/v1/legal-conversion-requests              列表（按角色过滤）
POST   /api/v1/legal-conversion-requests/{id}/approve 批准 → 创建 Order（复用 build_legal_conversion_order）
POST   /api/v1/legal-conversion-requests/{id}/reject  驳回（必填理由）
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.phone_visibility import (
    display_owner_phone,
    is_provider_contract_active,
    should_reveal_owner_phone,
)
from app.core.security import get_token_payload, require_roles
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.legal_conversion import LegalConversionRequest
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.legal_conversion_request import (
    ApproveLegalConversionRequestBody,
    LegalConversionRequestOut,
    RejectLegalConversionRequestBody,
)
from app.services.audit import log_audit

from .admin_legal_conversion import build_legal_conversion_order

router = APIRouter()

# 审批人角色：督导 / admin / platform_super
REVIEWER_ROLES = ("supervisor", "admin", "platform_super", "platform_superadmin")
# 申请人角色：催收员
REQUESTER_ROLES = ("agent_internal", "agent_external")
# 列表查看者：审批人 + 申请人（自己的）
VIEWER_ROLES = REVIEWER_ROLES + REQUESTER_ROLES


def _require_tenant(payload: dict) -> int:
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    return int(tenant_id)


def _row_to_out(
    *,
    request_row: LegalConversionRequest,
    case: CollectionCase | None,
    owner: OwnerProfile | None,
    project_name: str | None,
    requester_name: str | None,
    reviewer_name: str | None,
    owner_phone_reveal: bool = False,
) -> LegalConversionRequestOut:
    return LegalConversionRequestOut(
        id=request_row.id,
        tenant_id=request_row.tenant_id,
        case_id=request_row.case_id,
        owner_name=owner.name if owner else None,
        owner_phone_masked=display_owner_phone(
            owner.phone_enc if owner else None,
            reveal=owner_phone_reveal,
        ),
        building=owner.building if owner else None,
        room=owner.room if owner else None,
        project_id=case.project_id if case else None,
        project_name=project_name,
        amount_owed=case.amount_owed if case else None,
        months_overdue=case.months_overdue if case else None,
        case_stage=case.stage if case else None,
        requester_user_id=request_row.requester_user_id,
        requester_role=request_row.requester_role,
        requester_name=requester_name,
        reason=request_row.reason,
        status=request_row.status,
        reviewer_user_id=request_row.reviewer_user_id,
        reviewer_role=request_row.reviewer_role,
        reviewer_name=reviewer_name,
        reviewed_at=request_row.reviewed_at,
        reviewer_note=request_row.reviewer_note,
        related_order_id=request_row.related_order_id,
        created_at=request_row.created_at,
        updated_at=request_row.updated_at,
    )


def _load_request_with_context(
    db: Session, request_id: int, tenant_id: int
) -> tuple[
    LegalConversionRequest,
    CollectionCase | None,
    OwnerProfile | None,
    str | None,
    str | None,
    str | None,
]:
    """加载 request + case + owner + project_name + requester_name + reviewer_name."""
    row = db.execute(
        select(
            LegalConversionRequest,
            CollectionCase,
            OwnerProfile,
            Project.name.label("project_name"),
            UserAccount.name.label("requester_name"),
        )
        .outerjoin(CollectionCase, CollectionCase.id == LegalConversionRequest.case_id)
        .outerjoin(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .outerjoin(Project, Project.id == CollectionCase.project_id)
        .outerjoin(UserAccount, UserAccount.id == LegalConversionRequest.requester_user_id)
        .where(
            LegalConversionRequest.id == request_id,
            LegalConversionRequest.tenant_id == tenant_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "申请不存在"},
        )
    request_row, case, owner, project_name, requester_name = row
    reviewer_name: str | None = None
    if request_row.reviewer_user_id is not None:
        reviewer_name = db.execute(
            select(UserAccount.name).where(UserAccount.id == request_row.reviewer_user_id)
        ).scalar_one_or_none()
    return request_row, case, owner, project_name, requester_name, reviewer_name


@router.get(
    "/legal-conversion-requests",
    response_model=PaginatedResponse[LegalConversionRequestOut],
)
def list_requests(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*VIEWER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    status: str | None = Query(None, max_length=20),
    case_id: int | None = Query(None, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[LegalConversionRequestOut]:
    tenant_id = _require_tenant(payload)
    role = str(payload.get("role") or "")
    user_id = int(payload.get("user_id") or 0)

    base = (
        select(
            LegalConversionRequest,
            CollectionCase,
            OwnerProfile,
            Project.name.label("project_name"),
            UserAccount.name.label("requester_name"),
        )
        .outerjoin(CollectionCase, CollectionCase.id == LegalConversionRequest.case_id)
        .outerjoin(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .outerjoin(Project, Project.id == CollectionCase.project_id)
        .outerjoin(UserAccount, UserAccount.id == LegalConversionRequest.requester_user_id)
        .where(LegalConversionRequest.tenant_id == tenant_id)
    )
    count_stmt = select(func.count(LegalConversionRequest.id)).where(
        LegalConversionRequest.tenant_id == tenant_id
    )

    # 催收员只能看自己提交的；审批人看所有
    if role in REQUESTER_ROLES and role not in REVIEWER_ROLES:
        base = base.where(LegalConversionRequest.requester_user_id == user_id)
        count_stmt = count_stmt.where(LegalConversionRequest.requester_user_id == user_id)

    if status:
        base = base.where(LegalConversionRequest.status == status)
        count_stmt = count_stmt.where(LegalConversionRequest.status == status)
    if case_id:
        base = base.where(LegalConversionRequest.case_id == case_id)
        count_stmt = count_stmt.where(LegalConversionRequest.case_id == case_id)

    total = int(db.execute(count_stmt).scalar_one())
    rows = db.execute(
        base.order_by(desc(LegalConversionRequest.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    # 为已审批的行批量查 reviewer_name
    reviewer_ids = {r[0].reviewer_user_id for r in rows if r[0].reviewer_user_id}
    reviewer_names: dict[int, str] = {}
    if reviewer_ids:
        for uid, name in db.execute(
            select(UserAccount.id, UserAccount.name).where(UserAccount.id.in_(reviewer_ids))
        ).all():
            reviewer_names[int(uid)] = name

    # v1.7.0 — 列表层一次决策：申请审批流由 supervisor/admin 审，物业内部默认明文
    role = payload.get("role", "")
    contract_active = is_provider_contract_active(db, tenant_id, payload.get("provider_id"))
    owner_phone_reveal = should_reveal_owner_phone(role=role, contract_active=contract_active)
    items = [
        _row_to_out(
            request_row=r,
            case=c,
            owner=o,
            project_name=pn,
            requester_name=rn,
            reviewer_name=reviewer_names.get(r.reviewer_user_id) if r.reviewer_user_id else None,
            owner_phone_reveal=owner_phone_reveal,
        )
        for r, c, o, pn, rn in rows
    ]
    return PaginatedResponse[LegalConversionRequestOut](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/legal-conversion-requests/{request_id}/approve",
    response_model=LegalConversionRequestOut,
)
def approve_request(
    request_id: int,
    body: ApproveLegalConversionRequestBody,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*REVIEWER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionRequestOut:
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0) or None
    role = str(payload.get("role") or "")

    request_row, case, owner, project_name, requester_name, _ = _load_request_with_context(
        db, request_id, tenant_id
    )
    if request_row.status != "pending":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATUS",
                "message": f"申请当前状态 {request_row.status}，无法批准",
            },
        )
    if case is None:
        # FK ondelete=CASCADE 应保证 case 删除时 request 也删，理论上不可达
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_CASE_GONE", "message": "关联案件已不存在"},
        )

    # v1.9.0 — supervisor 审批通过后订单进物业法务内部处理（不直接派律所）
    order = build_legal_conversion_order(
        db,
        case=case,
        package_id=body.package_id,
        notes=body.notes,
        created_by_user_id=user_id,
        initial_status="internal_processing",
    )

    now = datetime.now(UTC)
    request_row.status = "approved"
    request_row.reviewer_user_id = user_id
    request_row.reviewer_role = role
    request_row.reviewed_at = now
    request_row.reviewer_note = body.notes
    request_row.related_order_id = order.id

    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=tenant_id,
        action="legal_conversion_request.approved",
        target_type="legal_conversion_request",
        target_id=request_id,
        payload={
            "case_id": request_row.case_id,
            "package_id": body.package_id,
            "order_id": order.id,
            "notes": body.notes,
        },
    )
    db.commit()
    db.refresh(request_row)
    reviewer_name = (
        db.execute(select(UserAccount.name).where(UserAccount.id == user_id)).scalar_one_or_none()
        if user_id
        else None
    )
    return _row_to_out(
        request_row=request_row,
        case=case,
        owner=owner,
        project_name=project_name,
        requester_name=requester_name,
        reviewer_name=reviewer_name,
        owner_phone_reveal=should_reveal_owner_phone(
            role=role,
            contract_active=is_provider_contract_active(db, tenant_id, payload.get("provider_id")),
        ),
    )


@router.post(
    "/legal-conversion-requests/{request_id}/reject",
    response_model=LegalConversionRequestOut,
)
def reject_request(
    request_id: int,
    body: RejectLegalConversionRequestBody,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*REVIEWER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionRequestOut:
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0) or None
    role = str(payload.get("role") or "")

    request_row, case, owner, project_name, requester_name, _ = _load_request_with_context(
        db, request_id, tenant_id
    )
    if request_row.status != "pending":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATUS",
                "message": f"申请当前状态 {request_row.status}，无法驳回",
            },
        )

    now = datetime.now(UTC)
    request_row.status = "rejected"
    request_row.reviewer_user_id = user_id
    request_row.reviewer_role = role
    request_row.reviewed_at = now
    request_row.reviewer_note = body.reason

    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=tenant_id,
        action="legal_conversion_request.rejected",
        target_type="legal_conversion_request",
        target_id=request_id,
        payload={"case_id": request_row.case_id, "reason": body.reason},
    )
    db.commit()
    db.refresh(request_row)
    reviewer_name = (
        db.execute(select(UserAccount.name).where(UserAccount.id == user_id)).scalar_one_or_none()
        if user_id
        else None
    )
    return _row_to_out(
        request_row=request_row,
        case=case,
        owner=owner,
        project_name=project_name,
        requester_name=requester_name,
        reviewer_name=reviewer_name,
        owner_phone_reveal=should_reveal_owner_phone(
            role=role,
            contract_active=is_provider_contract_active(db, tenant_id, payload.get("provider_id")),
        ),
    )
