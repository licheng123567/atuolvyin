from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone
from app.core.db import get_db
from app.core.security import get_token_payload, mask_phone, require_roles
from app.models.tenant import Tenant
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.services.audit import log_audit
from app.schemas.tenant import (
    TenantCreate,
    TenantDisableIn,
    TenantQuotaUpdate,
    TenantRenewIn,
    TenantResponse,
    TenantTrialOut,
)

router = APIRouter()

OPS_ROLES = ("platform_ops", "platform_superadmin", "platform_super")


def _tenant_to_response(tenant: Tenant) -> TenantResponse:
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        credit_code=tenant.credit_code,
        admin_phone_masked=mask_phone(tenant.admin_phone_enc),
        plan=tenant.plan,
        monthly_minute_quota=tenant.monthly_minute_quota,
        expires_at=tenant.expires_at,
        is_active=tenant.is_active,
        is_trial=tenant.is_trial,
        disabled_reason=tenant.disabled_reason,
        disabled_at=tenant.disabled_at,
        created_at=tenant.created_at,
    )


def _compute_days_remaining(expires_at: datetime | None) -> int | None:
    if expires_at is None:
        return None
    now = datetime.now(UTC)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    delta = expires_at - now
    # ceil-style days: anything > 0 today counts as 1 day remaining; <=0 = expired
    return max(0, delta.days + (1 if delta.seconds > 0 or delta.microseconds > 0 else 0))


def _trial_to_out(tenant: Tenant) -> TenantTrialOut:
    return TenantTrialOut(
        id=tenant.id,
        name=tenant.name,
        plan=tenant.plan,
        admin_phone_masked=mask_phone(tenant.admin_phone_enc),
        expires_at=tenant.expires_at,
        days_remaining=_compute_days_remaining(tenant.expires_at),
        is_active=tenant.is_active,
        created_at=tenant.created_at,
    )


def _load_tenant(db: Session, tenant_id: int) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "租户不存在"},
        )
    return tenant


@router.get("/tenants", response_model=PaginatedResponse[TenantResponse])
async def list_tenants(
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[TenantResponse]:
    stmt = select(Tenant)
    if q:
        stmt = stmt.where(Tenant.name.ilike(f"%{q}%"))
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(total_stmt).scalar_one()
    tenants = (
        db.execute(
            stmt.order_by(Tenant.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedResponse(
        items=[_tenant_to_response(t) for t in tenants],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/tenants", response_model=TenantResponse, status_code=201)
async def create_tenant(
    body: TenantCreate,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> TenantResponse:
    tenant = Tenant(
        name=body.name,
        credit_code=body.credit_code,
        admin_phone_enc=encrypt_phone(body.admin_phone),
        plan=body.plan,
        monthly_minute_quota=body.monthly_minute_quota,
        is_active=True,
        is_trial=(body.plan == "trial"),
    )
    db.add(tenant)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "code": "ERR_DUPLICATE_CREDIT_CODE",
                "message": "统一社会信用代码已存在",
            },
        ) from None
    log_audit(
        db,
        actor_user_id=int(payload.get("user_id") or 0) or None,
        actor_role=payload.get("role"),
        tenant_id=tenant.id,
        action="tenant.create",
        target_type="tenant",
        target_id=tenant.id,
        payload={"name": body.name, "plan": body.plan},
    )
    db.commit()
    db.refresh(tenant)
    return _tenant_to_response(tenant)


@router.get("/tenants/trial", response_model=PaginatedResponse[TenantTrialOut])
async def list_trial_tenants(
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[TenantTrialOut]:
    """试用账号跟进 — plan='trial' OR is_trial=True, sorted by days_remaining asc."""
    stmt = select(Tenant).where(
        (Tenant.plan == "trial") | (Tenant.is_trial.is_(True))
    )
    total: int = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()

    # Sort: NULL expires_at last, otherwise ascending (closest expiry first)
    rows = (
        db.execute(
            stmt.order_by(
                Tenant.expires_at.is_(None),  # False (has date) first
                Tenant.expires_at.asc(),
                Tenant.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedResponse(
        items=[_trial_to_out(t) for t in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: int,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TenantResponse:
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "租户不存在"},
        )
    return _tenant_to_response(tenant)


@router.patch("/tenants/{tenant_id}/quota", response_model=TenantResponse)
async def update_tenant_quota(
    tenant_id: int,
    body: TenantQuotaUpdate,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TenantResponse:
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "租户不存在"},
        )
    tenant.monthly_minute_quota = body.monthly_minute_quota
    tenant.minute_quota_updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(tenant)
    return _tenant_to_response(tenant)


@router.patch("/tenants/{tenant_id}/renew", response_model=TenantResponse)
async def renew_tenant(
    tenant_id: int,
    body: TenantRenewIn,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TenantResponse:
    """续费 / 变更套餐 — 共用 endpoint."""
    tenant = _load_tenant(db, tenant_id)
    tenant.expires_at = body.expires_at
    if body.plan is not None:
        tenant.plan = body.plan
        tenant.is_trial = body.plan == "trial"
    if body.monthly_minute_quota is not None:
        tenant.monthly_minute_quota = body.monthly_minute_quota
        tenant.minute_quota_updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(tenant)
    return _tenant_to_response(tenant)


@router.patch("/tenants/{tenant_id}/disable", response_model=TenantResponse)
async def disable_tenant(
    tenant_id: int,
    body: TenantDisableIn,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> TenantResponse:
    tenant = _load_tenant(db, tenant_id)
    tenant.is_active = False
    tenant.disabled_at = datetime.now(UTC)
    tenant.disabled_reason = body.reason
    log_audit(
        db,
        actor_user_id=int(payload.get("user_id") or 0) or None,
        actor_role=payload.get("role"),
        tenant_id=tenant.id,
        action="tenant.disable",
        target_type="tenant",
        target_id=tenant.id,
        payload={"reason": body.reason},
    )
    db.commit()
    db.refresh(tenant)
    return _tenant_to_response(tenant)


@router.patch("/tenants/{tenant_id}/enable", response_model=TenantResponse)
async def enable_tenant(
    tenant_id: int,
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> TenantResponse:
    tenant = _load_tenant(db, tenant_id)
    tenant.is_active = True
    tenant.disabled_at = None
    tenant.disabled_reason = None
    db.commit()
    db.refresh(tenant)
    return _tenant_to_response(tenant)
