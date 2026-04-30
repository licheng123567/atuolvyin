from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone
from app.core.db import get_db
from app.core.security import mask_phone, require_roles
from app.models.tenant import Tenant
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.tenant import TenantCreate, TenantQuotaUpdate, TenantResponse

router = APIRouter()

OPS_ROLES = ("platform_ops", "platform_superadmin")


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
        created_at=tenant.created_at,
    )


@router.get("/tenants", response_model=PaginatedResponse[TenantResponse])
async def list_tenants(
    _user: Annotated[UserAccount, Depends(require_roles(*OPS_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: Optional[str] = Query(None, max_length=100),
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
    db: Annotated[Session, Depends(get_db)],
) -> TenantResponse:
    tenant = Tenant(
        name=body.name,
        credit_code=body.credit_code,
        admin_phone_enc=encrypt_phone(body.admin_phone),
        plan=body.plan,
        monthly_minute_quota=body.monthly_minute_quota,
        is_active=True,
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
        )
    db.commit()
    db.refresh(tenant)
    return _tenant_to_response(tenant)


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
    tenant.minute_quota_updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(tenant)
    return _tenant_to_response(tenant)
