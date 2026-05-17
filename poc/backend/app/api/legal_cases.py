"""Sprint 13 — Legal Case management for `legal` role.

GET    /api/v1/legal/cases                              list w/ q + stage filters
POST   /api/v1/legal/cases                              create from collection_case_id
GET    /api/v1/legal/cases/{id}                         detail incl. collection_case ref
PATCH  /api/v1/legal/cases/{id}                         partial update
GET    /api/v1/legal/cases/{id}/evidence-bundle         Sprint 11.5 — ZIP 存证包
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.phone_visibility import (
    display_owner_phone,
    is_provider_contract_active,
    should_reveal_owner_phone,
)
from app.core.security import (
    get_token_payload,
    require_tenant_roles,
)
from app.models.case import CollectionCase, OwnerProfile
from app.models.user import UserAccount
from app.models.work import LegalCase
from app.schemas.common import PaginatedResponse
from app.schemas.legal import (
    CollectionCaseRef,
    LegalCaseCreate,
    LegalCaseDetailOut,
    LegalCaseOut,
    LegalCasePatch,
)

router = APIRouter()

LEGAL_ROLES = ("legal", "admin")


def _require_tenant(payload: dict) -> int:
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )
    return tenant_id


def _legal_to_out(
    lc: LegalCase,
    owner_name: str | None,
    phone_enc: str | None,
    *,
    viewer_role: str = "",
    viewer_provider_id: int | None = None,
    contract_active: bool = False,
) -> LegalCaseOut:
    """v2.2 — owner_phone_masked 字段值动态：legal 看 stage 是否在 active 集合，
    内部物业/admin 永远明文，平台永远脱敏。
    """
    reveal = should_reveal_owner_phone(
        role=viewer_role,
        provider_id=viewer_provider_id,
        contract_active=contract_active,
        legal_case_stage=lc.stage,
    )
    return LegalCaseOut(
        id=lc.id,
        tenant_id=lc.tenant_id,
        case_id=lc.case_id,
        stage=lc.stage,
        amount_disputed=lc.amount_disputed,
        lawyer_name=lc.lawyer_name,
        law_firm=lc.law_firm,
        next_milestone=lc.next_milestone,
        notes=lc.notes,
        created_at=lc.created_at,
        updated_at=lc.updated_at,
        owner_name=owner_name,
        owner_phone_masked=display_owner_phone(phone_enc, reveal=reveal),
    )


@router.get("/cases", response_model=PaginatedResponse[LegalCaseOut])
async def list_legal_cases(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None, max_length=100),
    stage: str | None = Query(None, max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[LegalCaseOut]:
    tenant_id = _require_tenant(payload)

    stmt = (
        select(LegalCase, OwnerProfile.name, OwnerProfile.phone_enc)
        .join(CollectionCase, CollectionCase.id == LegalCase.case_id)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(LegalCase.tenant_id == tenant_id)
    )
    if stage:
        stmt = stmt.where(LegalCase.stage == stage)
    if q:
        stmt = stmt.where(OwnerProfile.name.ilike(f"%{q}%"))

    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    rows = db.execute(
        stmt.order_by(LegalCase.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    role = payload.get("role", "")
    contract_active = is_provider_contract_active(db, tenant_id, payload.get("provider_id"))
    items = [
        _legal_to_out(lc, name, phone_enc, viewer_role=role, viewer_provider_id=payload.get("provider_id"), contract_active=contract_active)
        for lc, name, phone_enc in rows
    ]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/cases",
    response_model=LegalCaseOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_legal_case(
    body: LegalCaseCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalCaseOut:
    tenant_id = _require_tenant(payload)

    # Verify the source collection_case is in this tenant
    cc = db.get(CollectionCase, body.case_id)
    if cc is None or cc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_CASE_NOT_FOUND", "message": "源案件不存在"},
        )

    lc = LegalCase(
        tenant_id=tenant_id,
        case_id=body.case_id,
        stage=body.stage,
        amount_disputed=body.amount_disputed,
        notes=body.notes,
        lawyer_name=body.lawyer_name,
        law_firm=body.law_firm,
        next_milestone=body.next_milestone,
    )
    db.add(lc)
    db.commit()
    db.refresh(lc)

    owner = db.get(OwnerProfile, cc.owner_id)
    return _legal_to_out(
        lc,
        owner.name if owner else None,
        owner.phone_enc if owner else None,
        viewer_role=payload.get("role", ""),
        viewer_provider_id=payload.get("provider_id"),
        contract_active=is_provider_contract_active(db, tenant_id, payload.get("provider_id")),
    )


@router.get("/cases/{legal_case_id}", response_model=LegalCaseDetailOut)
async def get_legal_case(
    legal_case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalCaseDetailOut:
    tenant_id = _require_tenant(payload)

    lc = db.get(LegalCase, legal_case_id)
    if lc is None or lc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "法务案件不存在"},
        )

    cc = db.get(CollectionCase, lc.case_id)
    owner = db.get(OwnerProfile, cc.owner_id) if cc else None

    role = payload.get("role", "")
    contract_active = is_provider_contract_active(db, tenant_id, payload.get("provider_id"))
    reveal = should_reveal_owner_phone(
        role=role,
        provider_id=payload.get("provider_id"),
        contract_active=contract_active,
        legal_case_stage=lc.stage,
    )

    base = _legal_to_out(
        lc,
        owner.name if owner else None,
        owner.phone_enc if owner else None,
        viewer_role=role,
        viewer_provider_id=payload.get("provider_id"),
        contract_active=contract_active,
    )

    cc_ref: CollectionCaseRef | None = None
    if cc and owner:
        cc_ref = CollectionCaseRef(
            id=cc.id,
            stage=cc.stage,
            amount_owed=cc.amount_owed,
            months_overdue=cc.months_overdue,
            owner_name=owner.name,
            owner_phone_masked=display_owner_phone(owner.phone_enc, reveal=reveal) or "",
        )

    return LegalCaseDetailOut(**base.model_dump(), collection_case=cc_ref)


@router.patch("/cases/{legal_case_id}", response_model=LegalCaseOut)
async def patch_legal_case(
    legal_case_id: int,
    body: LegalCasePatch,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> LegalCaseOut:
    tenant_id = _require_tenant(payload)

    lc = db.get(LegalCase, legal_case_id)
    if lc is None or lc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "法务案件不存在"},
        )

    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(lc, field, value)

    db.commit()
    db.refresh(lc)

    cc = db.get(CollectionCase, lc.case_id)
    owner = db.get(OwnerProfile, cc.owner_id) if cc else None
    return _legal_to_out(
        lc,
        owner.name if owner else None,
        owner.phone_enc if owner else None,
        viewer_role=payload.get("role", ""),
        viewer_provider_id=payload.get("provider_id"),
        contract_active=is_provider_contract_active(db, tenant_id, payload.get("provider_id")),
    )


# ── Sprint 11.5 — Evidence bundle ZIP download (PRD §L2135) ─────────


@router.get("/cases/{legal_case_id}/evidence-bundle")
async def download_evidence_bundle(
    legal_case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_tenant_roles(*LEGAL_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> StreamingResponse:
    # v1.9.5 — 复用 services/evidence_bundle.py 的统一构建器
    from app.services.evidence_bundle import build_evidence_bundle_zip

    tenant_id = _require_tenant(payload)
    user_id = int(payload.get("user_id") or 0)

    lc = db.get(LegalCase, legal_case_id)
    if lc is None or lc.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "法务案件不存在"},
        )
    cc = db.get(CollectionCase, lc.case_id)
    owner = db.get(OwnerProfile, cc.owner_id) if cc else None
    if not cc or not owner:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件或业主信息缺失"},
        )

    reveal = should_reveal_owner_phone(
        role=payload.get("role", ""),
        provider_id=payload.get("provider_id"),
        contract_active=is_provider_contract_active(db, tenant_id, payload.get("provider_id")),
        legal_case_stage=lc.stage,
    )
    buffer, filename = build_evidence_bundle_zip(
        db,
        tenant_id=tenant_id,
        case=cc,
        owner=owner,
        owner_phone_display=display_owner_phone(owner.phone_enc, reveal=reveal),
        case_summary_extra={
            "legal_stage": lc.stage,
            "lawyer_name": lc.lawyer_name,
            "law_firm": lc.law_firm,
            "next_milestone": lc.next_milestone,
        },
        user_id=user_id or None,
        legal_case_id=lc.id,
    )
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
