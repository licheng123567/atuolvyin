"""v1.6.8 — 法务转化申请审批 API.

催收员通过 `POST /agent/cases/{id}/intent action=transfer_legal` 提交申请
（写入 LegalConversionRequest），督导/admin 在此 inbox 审批。

v0.5.4 起,审批流改为三层模型 + 法务接单选包:
  pending(督导待审)→ 督导批准 / 拒绝 / 上报 admin(pending_admin)
  pending_admin → admin 批准 / 拒绝
  批准后状态 approved_pending_legal,等物业法务在 /legal-finalize 选服务包 → Order 创建 + 状态 approved

GET    /api/v1/legal-conversion-requests                       列表（按角色过滤）
POST   /api/v1/legal-conversion-requests/{id}/approve          批准（不选服务包,改流到法务接单）
POST   /api/v1/legal-conversion-requests/{id}/reject           驳回（必填理由）
POST   /api/v1/legal-conversion-requests/{id}/escalate-to-admin 督导上报 admin
POST   /api/v1/legal-conversion-requests/{id}/legal-finalize   法务接单选包 → 建 Order
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
from app.core.security import get_token_payload, require_roles, require_tenant_roles
from app.core.storage import storage
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.legal_conversion import (
    LegalConversionOrder,
    LegalConversionRequest,
    LegalConversionRequestMaterial,
)
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.legal_conversion_request import (
    ApproveLegalConversionRequestBody,
    FinalizeLegalConversionRequestBody,
    LegalConversionRequestDetailOut,
    LegalConversionRequestMaterialDownloadOut,
    LegalConversionRequestMaterialOut,
    LegalConversionRequestOut,
    RejectLegalConversionRequestBody,
)
from app.services.audit import log_audit

from .admin_legal_conversion import build_legal_conversion_order

router = APIRouter()

# 审批人角色：督导 / admin / superadmin
REVIEWER_ROLES = ("supervisor", "admin", "superadmin")
# 申请人角色：催收员
REQUESTER_ROLES = ("agent",)
# v0.5.4 — 物业法务角色:接「approved_pending_legal」请求选服务包建 Order
LEGAL_ROLES = ("legal",)
# 列表查看者：审批人 + 申请人（自己的）+ 法务（仅看待接单的）
VIEWER_ROLES = REVIEWER_ROLES + REQUESTER_ROLES + LEGAL_ROLES


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
    # v0.5.4 — 物业法务只看「待法务接单」(approved_pending_legal) 的请求
    if role in LEGAL_ROLES and role not in REVIEWER_ROLES:
        base = base.where(LegalConversionRequest.status == "approved_pending_legal")
        count_stmt = count_stmt.where(
            LegalConversionRequest.status == "approved_pending_legal"
        )

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
    owner_phone_reveal = should_reveal_owner_phone(role=role, provider_id=payload.get("provider_id"), contract_active=contract_active)
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
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*REVIEWER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionRequestOut:
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0) or None
    role = str(payload.get("role") or "")

    request_row, case, owner, project_name, requester_name, _ = _load_request_with_context(
        db, request_id, tenant_id
    )
    # v0.5.4 — 三层审批模型:
    #   pending(督导待审)→ 督导批 → approved_pending_legal(待法务接单选包)
    #   pending_admin(督导上报后)→ admin 批 → approved_pending_legal
    if request_row.status not in {"pending", "pending_admin"}:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATUS",
                "message": f"申请当前状态 {request_row.status}，无法批准",
            },
        )
    if request_row.status == "pending" and role != "supervisor":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NOT_SUPERVISOR", "message": "督导待审单需督导批准"},
        )
    if request_row.status == "pending_admin" and role != "admin":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NOT_ADMIN", "message": "admin 待审单需 admin 批准"},
        )
    if case is None:
        # FK ondelete=CASCADE 应保证 case 删除时 request 也删，理论上不可达
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_CASE_GONE", "message": "关联案件已不存在"},
        )

    # v0.5.4 — 不再在此处建 Order;status → approved_pending_legal 等法务接单选包
    # (旧 v1.9.0 流程:这里 build_legal_conversion_order(initial_status="internal_processing"))
    now = datetime.now(UTC)
    request_row.status = "approved_pending_legal"
    request_row.reviewer_user_id = user_id
    request_row.reviewer_role = role
    request_row.reviewed_at = now
    request_row.reviewer_note = body.notes

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
            "notes": body.notes,
            "new_status": "approved_pending_legal",
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
            provider_id=payload.get("provider_id"),
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
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*REVIEWER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionRequestOut:
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0) or None
    role = str(payload.get("role") or "")

    request_row, case, owner, project_name, requester_name, _ = _load_request_with_context(
        db, request_id, tenant_id
    )
    # v0.5.4 — pending(督导)/ pending_admin(admin)均可驳回;按角色匹配
    if request_row.status not in {"pending", "pending_admin"}:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATUS",
                "message": f"申请当前状态 {request_row.status}，无法驳回",
            },
        )
    if request_row.status == "pending" and role != "supervisor":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NOT_SUPERVISOR", "message": "督导待审单需督导驳回"},
        )
    if request_row.status == "pending_admin" and role != "admin":
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NOT_ADMIN", "message": "admin 待审单需 admin 驳回"},
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
            provider_id=payload.get("provider_id"),
            contract_active=is_provider_contract_active(db, tenant_id, payload.get("provider_id")),
        ),
    )


# ── v0.5.4 — 督导上报 admin ────────────────────────────────────────


@router.post(
    "/legal-conversion-requests/{request_id}/escalate-to-admin",
    response_model=LegalConversionRequestOut,
)
def escalate_request_to_admin(
    request_id: int,
    body: RejectLegalConversionRequestBody,  # 复用:reason 字段 = 上报理由
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles("supervisor"))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionRequestOut:
    """v0.5.4 — 督导对超出自己决断范围的转法务申请,主动上报给 admin 审批。

    pending → pending_admin,写 escalated_to_admin_at。
    """
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
                "message": f"申请当前状态 {request_row.status},无法上报 admin",
            },
        )

    now = datetime.now(UTC)
    request_row.status = "pending_admin"
    request_row.escalated_to_admin_at = now
    # 上报理由写入 reviewer_note,以便 admin 阅读;reviewer_user_id 此时不写(admin 才是 reviewer)
    request_row.reviewer_note = f"督导上报: {body.reason}"

    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=tenant_id,
        action="legal_conversion_request.escalated_to_admin",
        target_type="legal_conversion_request",
        target_id=request_id,
        payload={"case_id": request_row.case_id, "reason": body.reason},
    )
    db.commit()
    db.refresh(request_row)
    reviewer_name = (
        db.execute(select(UserAccount.name).where(UserAccount.id == request_row.reviewer_user_id)).scalar_one_or_none()
        if request_row.reviewer_user_id
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
            provider_id=payload.get("provider_id"),
            contract_active=is_provider_contract_active(db, tenant_id, payload.get("provider_id")),
        ),
    )


# ── v0.5.4 — 法务接单选服务包(approved_pending_legal → approved + 建 Order)──


@router.post(
    "/legal-conversion-requests/{request_id}/legal-finalize",
    response_model=LegalConversionRequestOut,
)
def legal_finalize_request(
    request_id: int,
    body: FinalizeLegalConversionRequestBody,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles("legal"))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionRequestOut:
    """v0.5.4 — 物业法务接「已批准待法务接单」的转法务请求,选服务包后建 Order。

    approved_pending_legal → approved + related_order_id;同时建 LegalConversionOrder。
    """
    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0) or None
    role = str(payload.get("role") or "")

    request_row, case, owner, project_name, requester_name, _ = _load_request_with_context(
        db, request_id, tenant_id
    )
    if request_row.status != "approved_pending_legal":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_STATUS",
                "message": f"申请当前状态 {request_row.status},非「待法务接单」",
            },
        )
    if case is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_CASE_GONE", "message": "关联案件已不存在"},
        )

    # 建 Order(沿用 v1.9.0 流程:initial_status='internal_processing'物业法务内部处理)
    order = build_legal_conversion_order(
        db,
        case=case,
        package_id=body.package_id,
        notes=body.notes,
        created_by_user_id=user_id,
        initial_status="internal_processing",
    )

    request_row.status = "approved"
    request_row.related_order_id = order.id
    # 不覆盖 reviewer_*(那是督导/admin 审批人记录);法务接单的备注追加到 reviewer_note
    if body.notes:
        prefix = request_row.reviewer_note or ""
        sep = "\n— 法务接单: " if prefix else "法务接单: "
        request_row.reviewer_note = f"{prefix}{sep}{body.notes}"

    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=role,
        tenant_id=tenant_id,
        action="legal_conversion_request.legal_finalized",
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
        db.execute(select(UserAccount.name).where(UserAccount.id == request_row.reviewer_user_id)).scalar_one_or_none()
        if request_row.reviewer_user_id
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
            provider_id=payload.get("provider_id"),
            contract_active=is_provider_contract_active(db, tenant_id, payload.get("provider_id")),
        ),
    )


@router.get(
    "/legal-conversion-requests/{request_id}",
    response_model=LegalConversionRequestDetailOut,
)
def get_request_detail(
    request_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*REVIEWER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionRequestDetailOut:
    """§9.1 — 物业审批人看请求详情 + 服务商法务上传的补充材料。"""
    tenant_id = _require_tenant(payload)
    (
        request_row,
        case,
        owner,
        project_name,
        requester_name,
        reviewer_name,
    ) = _load_request_with_context(db, request_id, tenant_id)
    contract_active = is_provider_contract_active(
        db, tenant_id, payload.get("provider_id")
    )
    owner_phone_reveal = should_reveal_owner_phone(
        role=payload.get("role", ""),
        provider_id=payload.get("provider_id"),
        contract_active=contract_active,
    )
    base = _row_to_out(
        request_row=request_row,
        case=case,
        owner=owner,
        project_name=project_name,
        requester_name=requester_name,
        reviewer_name=reviewer_name,
        owner_phone_reveal=owner_phone_reveal,
    )
    order_status: str | None = None
    if request_row.related_order_id is not None:
        order = db.get(LegalConversionOrder, request_row.related_order_id)
        order_status = order.status if order else None
    materials = (
        db.execute(
            select(LegalConversionRequestMaterial)
            .where(LegalConversionRequestMaterial.request_id == request_id)
            .order_by(LegalConversionRequestMaterial.id)
        )
        .scalars()
        .all()
    )
    return LegalConversionRequestDetailOut(
        **base.model_dump(),
        order_status=order_status,
        materials=[
            LegalConversionRequestMaterialOut.model_validate(m) for m in materials
        ],
    )


@router.get(
    "/legal-conversion-requests/{request_id}/materials/{material_id}",
    response_model=LegalConversionRequestMaterialDownloadOut,
)
def download_request_material(
    request_id: int,
    material_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*REVIEWER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionRequestMaterialDownloadOut:
    """§9.1 — 物业审批人下载服务商法务上传的补充材料。"""
    tenant_id = _require_tenant(payload)
    material = db.get(LegalConversionRequestMaterial, material_id)
    if (
        material is None
        or material.request_id != request_id
        or material.tenant_id != tenant_id
    ):
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "材料不存在"},
        )
    try:
        url = storage.get_url(material.object_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail={"code": "ERR_STORAGE_FAILURE", "message": "无法生成下载链接"},
        ) from exc
    return LegalConversionRequestMaterialDownloadOut(
        download_url=url,
        filename=material.filename,
        content_type=material.content_type,
        size_bytes=material.size_bytes,
    )
