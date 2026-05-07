"""Sprint 11 — platform_ops Service Provider management.

GET    /api/v1/ops/providers                 list w/ q + audit_status filters
POST   /api/v1/ops/providers                 create (status=pending, 201)
GET    /api/v1/ops/providers/{id}            detail + contracts[]
PATCH  /api/v1/ops/providers/{id}/audit      approve / reject (pending only)
PATCH  /api/v1/ops/providers/{id}            partial update
PATCH  /api/v1/ops/providers/{id}/active     toggle is_active
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone, mask_phone
from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.tenant import (
    ProviderTenantContract,
    ServiceProvider,
    Tenant,
)
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.provider import (
    ProviderActiveIn,
    ProviderAuditIn,
    ProviderContractItem,
    ProviderCreate,
    ProviderDetailOut,
    ProviderOut,
    ProviderPatch,
)
from app.services.audit import log_audit

router = APIRouter()

OPS_ROLES = ("platform_ops", "platform_superadmin", "platform_super")


def _provider_to_out(
    p: ServiceProvider, recommended_by_tenant_name: str | None = None
) -> ProviderOut:
    return ProviderOut(
        id=p.id,
        name=p.name,
        provider_type=p.provider_type,
        admin_phone_masked=mask_phone(p.admin_phone_enc),
        contact_email=p.contact_email,
        description=p.description,
        monthly_minute_quota=p.monthly_minute_quota,
        is_active=p.is_active,
        audit_status=p.audit_status,
        audit_reason=p.audit_reason,
        audit_at=p.audit_at,
        created_at=p.created_at,
        recommended_by_tenant_id=p.recommended_by_tenant_id,
        recommended_by_tenant_name=recommended_by_tenant_name,
    )


def _load_provider(db: Session, provider_id: int) -> ServiceProvider:
    p = db.get(ServiceProvider, provider_id)
    if p is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "服务商不存在"},
        )
    return p


@router.get("/providers", response_model=PaginatedResponse[ProviderOut])
async def list_providers(
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None, max_length=100),
    audit_status: str | None = Query(None, pattern=r"^(pending|approved|rejected)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ProviderOut]:
    stmt = select(ServiceProvider)
    if q:
        # Phones are deterministically encrypted, so an exact full-phone query
        # can be looked up by encrypting the value; substrings fall back to name.
        if q.isdigit() and len(q) == 11:
            stmt = stmt.where(
                or_(
                    ServiceProvider.name.ilike(f"%{q}%"),
                    ServiceProvider.admin_phone_enc == encrypt_phone(q),
                )
            )
        else:
            stmt = stmt.where(ServiceProvider.name.ilike(f"%{q}%"))
    if audit_status:
        stmt = stmt.where(ServiceProvider.audit_status == audit_status)

    total: int = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()

    rows = (
        db.execute(
            stmt.order_by(ServiceProvider.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    # 推荐人 tenant_name 一次性查（v1.4 — D1 溯源）
    recommender_ids = [
        p.recommended_by_tenant_id for p in rows if p.recommended_by_tenant_id
    ]
    tenant_name_by_id: dict[int, str] = {}
    if recommender_ids:
        tenant_name_by_id = dict(
            db.execute(
                select(Tenant.id, Tenant.name).where(Tenant.id.in_(recommender_ids))
            ).all()
        )

    return PaginatedResponse(
        items=[
            _provider_to_out(
                p, tenant_name_by_id.get(p.recommended_by_tenant_id or 0)
            )
            for p in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/providers",
    response_model=ProviderOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_provider(
    body: ProviderCreate,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderOut:
    p = ServiceProvider(
        name=body.name,
        provider_type=body.provider_type,
        admin_phone_enc=encrypt_phone(body.admin_phone),
        contact_email=body.contact_email,
        description=body.description,
        monthly_minute_quota=body.monthly_minute_quota,
        is_active=True,
        audit_status="pending",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _provider_to_out(p)


@router.get("/providers/{provider_id}", response_model=ProviderDetailOut)
async def get_provider(
    provider_id: int,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderDetailOut:
    p = _load_provider(db, provider_id)

    recommender_name: str | None = None
    if p.recommended_by_tenant_id:
        recommender_name = db.execute(
            select(Tenant.name).where(Tenant.id == p.recommended_by_tenant_id)
        ).scalar_one_or_none()

    rows = db.execute(
        select(ProviderTenantContract, Tenant.name)
        .join(Tenant, Tenant.id == ProviderTenantContract.tenant_id)
        .where(ProviderTenantContract.provider_id == provider_id)
        .order_by(ProviderTenantContract.id.desc())
    ).all()

    contracts = [
        ProviderContractItem(
            id=c.id,
            tenant_id=c.tenant_id,
            tenant_name=tname,
            signed_at=c.signed_at,
            expires_at=c.expires_at,
            service_types=list(c.service_types or []),
            status=c.status,
        )
        for c, tname in rows
    ]

    base = _provider_to_out(p, recommender_name)
    return ProviderDetailOut(**base.model_dump(), contracts=contracts)


@router.patch("/providers/{provider_id}/audit", response_model=ProviderOut)
async def audit_provider(
    provider_id: int,
    body: ProviderAuditIn,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderOut:
    p = _load_provider(db, provider_id)

    if p.audit_status != "pending":
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_INVALID_TRANSITION",
                "message": "仅待审核状态可执行此操作",
            },
        )

    p.audit_status = body.decision
    p.audit_reason = body.reason
    p.audit_at = datetime.now(UTC)
    log_audit(
        db,
        actor_user_id=int(payload.get("user_id") or 0) or None,
        actor_role=payload.get("role"),
        tenant_id=None,
        action="provider.audit",
        target_type="provider",
        target_id=p.id,
        payload={"decision": body.decision, "reason": body.reason},
    )
    db.commit()
    db.refresh(p)
    return _provider_to_out(p)


@router.patch("/providers/{provider_id}", response_model=ProviderOut)
async def patch_provider(
    provider_id: int,
    body: ProviderPatch,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderOut:
    p = _load_provider(db, provider_id)

    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(p, field, value)

    db.commit()
    db.refresh(p)
    return _provider_to_out(p)


@router.patch("/providers/{provider_id}/active", response_model=ProviderOut)
async def toggle_provider_active(
    provider_id: int,
    body: ProviderActiveIn,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ProviderOut:
    p = _load_provider(db, provider_id)
    p.is_active = body.is_active
    db.commit()
    db.refresh(p)
    return _provider_to_out(p)
