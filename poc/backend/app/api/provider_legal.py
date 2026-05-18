"""§9.1 — 服务商法务职责边界。

服务商侧法务（role='legal' + provider_id 非空）专用端点。整路由用
require_provider_roles("legal") 守卫；案件归属经 CollectionCase.project_id →
Project.provider_id 推导。物业侧 legal 端点不受影响。
"""
from __future__ import annotations

import uuid
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi import status as http_status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.phone_visibility import display_owner_phone, should_reveal_owner_phone
from app.core.roles import ROLE_LEGAL
from app.core.security import get_token_payload, require_provider_roles
from app.core.storage import storage
from app.models.call import CallRecord
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.legal_conversion import (
    LegalConversionOrder,
    LegalConversionRequest,
    LegalConversionRequestMaterial,
)
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.legal_conversion_request import (
    LegalConversionRequestMaterialDownloadOut,
    LegalConversionRequestMaterialOut,
)
from app.schemas.provider_legal import (
    ProviderLegalCaseDetail,
    ProviderLegalCaseListItem,
    ProviderLegalConversionRequestCreate,
    ProviderLegalRequestDetail,
    ProviderLegalRequestOut,
)
from app.services.audit import log_audit

# §9.1 — 复用 legal_documents 的文件大小 / MIME 白名单常量，避免漂移（设计 §4.1）
from .legal_documents import ALLOWED_MIME_PREFIXES, MAX_DOC_SIZE

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
    keyword: str | None = Query(None, max_length=100),
) -> PaginatedResponse[ProviderLegalCaseListItem]:
    tenant_id, provider_id, _ = _ctx(payload)
    case_filter = _provider_legal_case_filter(tenant_id, provider_id)

    stmt = (
        select(CollectionCase, OwnerProfile, Project.name.label("project_name"))
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .outerjoin(Project, Project.id == CollectionCase.project_id)
        .where(case_filter)
    )

    kw = keyword.strip() if keyword else ""
    if kw:
        room_concat = func.concat(
            func.coalesce(OwnerProfile.building, ""),
            func.coalesce(OwnerProfile.room, ""),
        )
        kw_filter = sa.or_(
            OwnerProfile.name.ilike(f"%{kw}%"),
            room_concat.ilike(f"%{kw}%"),
        )
        stmt = stmt.where(kw_filter)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(db.execute(count_stmt).scalar_one())

    rows = db.execute(
        stmt.order_by(desc(CollectionCase.id))
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


def _request_to_out(db: Session, req: LegalConversionRequest) -> ProviderLegalRequestOut:
    """把 LegalConversionRequest 组装成 ProviderLegalRequestOut（含订单高阶状态）。"""
    case = db.get(CollectionCase, req.case_id)
    owner = db.get(OwnerProfile, case.owner_id) if case else None
    project = db.get(Project, case.project_id) if case and case.project_id else None
    order_status: str | None = None
    if req.related_order_id is not None:
        order = db.get(LegalConversionOrder, req.related_order_id)
        order_status = order.status if order else None
    return ProviderLegalRequestOut(
        id=req.id,
        tenant_id=req.tenant_id,
        case_id=req.case_id,
        owner_name=owner.name if owner else None,
        project_id=case.project_id if case else None,
        project_name=project.name if project else None,
        amount_owed=case.amount_owed if case else None,
        reason=req.reason,
        status=req.status,
        reviewer_note=req.reviewer_note,
        reviewed_at=req.reviewed_at,
        related_order_id=req.related_order_id,
        order_status=order_status,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


@router.post(
    "/cases/{case_id}/conversion-request",
    response_model=ProviderLegalRequestOut,
    status_code=http_status.HTTP_201_CREATED,
)
def create_conversion_request(
    case_id: int,
    body: ProviderLegalConversionRequestCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(ROLE_LEGAL))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderLegalRequestOut:
    tenant_id, provider_id, user_id = _ctx(payload)
    case = db.execute(
        select(CollectionCase).where(
            CollectionCase.id == case_id,
            _provider_legal_case_filter(tenant_id, provider_id),
        )
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    active_order = db.execute(
        select(LegalConversionOrder).where(
            LegalConversionOrder.case_id == case_id,
            LegalConversionOrder.status.in_(("pending", "dispatched", "in_service")),
        )
    ).scalar_one_or_none()
    if active_order is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_LEGAL_ORDER_EXISTS",
                "message": "该案件已存在进行中的法务转化订单",
            },
        )
    pending_req = db.execute(
        select(LegalConversionRequest).where(
            LegalConversionRequest.case_id == case_id,
            LegalConversionRequest.status == "pending",
        )
    ).scalar_one_or_none()
    if pending_req is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_REQUEST_PENDING",
                "message": "该案件已有待审批的转法务申请",
            },
        )
    req = LegalConversionRequest(
        tenant_id=tenant_id,
        case_id=case_id,
        requester_user_id=user_id,
        requester_role=ROLE_LEGAL,
        reason=body.reason,
        status="pending",
    )
    db.add(req)
    db.flush()
    log_audit(
        db,
        actor_user_id=user_id,
        actor_role=ROLE_LEGAL,
        tenant_id=tenant_id,
        action="legal_conversion_request.created",
        target_type="legal_conversion_request",
        target_id=req.id,
        payload={"case_id": case_id, "reason": body.reason}
        if body.reason
        else {"case_id": case_id},
    )
    db.commit()
    db.refresh(req)
    return _request_to_out(db, req)


def _load_provider_request(
    db: Session, request_id: int, tenant_id: int, provider_id: int
) -> LegalConversionRequest:
    """加载请求并校验其案件在本服务商作用域内；不在则 404。"""
    req = db.execute(
        select(LegalConversionRequest)
        .join(CollectionCase, CollectionCase.id == LegalConversionRequest.case_id)
        .where(
            LegalConversionRequest.id == request_id,
            LegalConversionRequest.tenant_id == tenant_id,
            _provider_legal_case_filter(tenant_id, provider_id),
        )
    ).scalar_one_or_none()
    if req is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "请求不存在"},
        )
    return req


@router.post(
    "/conversion-requests/{request_id}/materials",
    response_model=LegalConversionRequestMaterialOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def upload_material(
    request_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(ROLE_LEGAL))],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
) -> LegalConversionRequestMaterialOut:
    tenant_id, provider_id, user_id = _ctx(payload)
    req = _load_provider_request(db, request_id, tenant_id, provider_id)
    if req.status != "pending":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_REQUEST_NOT_PENDING",
                "message": "请求已审批，材料已锁定",
            },
        )
    mime = file.content_type or ""
    if mime and not any(mime.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_INVALID_MIME", "message": f"不支持的文件类型: {mime}"},
        )
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_EMPTY_FILE", "message": "上传文件为空"},
        )
    if len(raw) > MAX_DOC_SIZE:
        raise HTTPException(
            status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "ERR_FILE_TOO_LARGE", "message": "文件超过 50MB 限制"},
        )
    filename = file.filename or f"material_{uuid.uuid4().hex[:8]}"
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    ext = "".join(c for c in ext if c.isalnum())[:10] or "bin"
    object_key = f"legal_conv_req_materials/{tenant_id}/{request_id}/{uuid.uuid4().hex}.{ext}"
    try:
        storage.put_object(object_key, raw, mime or "application/octet-stream")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail={"code": "ERR_STORAGE_FAILURE", "message": "文件存储失败"},
        ) from exc
    material = LegalConversionRequestMaterial(
        request_id=request_id,
        tenant_id=tenant_id,
        object_key=object_key,
        filename=filename,
        content_type=mime or None,
        size_bytes=len(raw),
        uploaded_by=user_id,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return LegalConversionRequestMaterialOut.model_validate(material)


@router.get(
    "/conversion-requests/{request_id}/materials/{material_id}",
    response_model=LegalConversionRequestMaterialDownloadOut,
)
def download_material(
    request_id: int,
    material_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(ROLE_LEGAL))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalConversionRequestMaterialDownloadOut:
    tenant_id, provider_id, _ = _ctx(payload)
    _load_provider_request(db, request_id, tenant_id, provider_id)
    material = db.get(LegalConversionRequestMaterial, material_id)
    if material is None or material.request_id != request_id:
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


@router.get(
    "/conversion-requests",
    response_model=PaginatedResponse[ProviderLegalRequestOut],
)
def list_conversion_requests(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(ROLE_LEGAL))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ProviderLegalRequestOut]:
    tenant_id, provider_id, _ = _ctx(payload)
    req_filter = sa.and_(
        LegalConversionRequest.tenant_id == tenant_id,
        LegalConversionRequest.case_id.in_(
            select(CollectionCase.id).where(
                _provider_legal_case_filter(tenant_id, provider_id)
            )
        ),
    )
    total = int(
        db.execute(
            select(func.count(LegalConversionRequest.id)).where(req_filter)
        ).scalar_one()
    )
    reqs = (
        db.execute(
            select(LegalConversionRequest)
            .where(req_filter)
            .order_by(desc(LegalConversionRequest.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    # 技术债：_request_to_out 每行最多 4 次 db.get（case/owner/project/order）。
    # page_size ≤ 100、且同页请求多共享 case/project（命中 identity map），PoC 可接受；
    # 若 page_size 上限提高需改为批量 join 取数。
    items = [_request_to_out(db, r) for r in reqs]
    return PaginatedResponse[ProviderLegalRequestOut](
        items=items, total=total, page=page, page_size=page_size
    )


@router.get(
    "/conversion-requests/{request_id}",
    response_model=ProviderLegalRequestDetail,
)
def get_conversion_request(
    request_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_provider_roles(ROLE_LEGAL))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderLegalRequestDetail:
    tenant_id, provider_id, _ = _ctx(payload)
    req = _load_provider_request(db, request_id, tenant_id, provider_id)
    materials = (
        db.execute(
            select(LegalConversionRequestMaterial)
            .where(LegalConversionRequestMaterial.request_id == request_id)
            .order_by(LegalConversionRequestMaterial.id)
        )
        .scalars()
        .all()
    )
    base = _request_to_out(db, req)
    return ProviderLegalRequestDetail(
        **base.model_dump(),
        materials=[
            LegalConversionRequestMaterialOut.model_validate(m) for m in materials
        ],
    )
