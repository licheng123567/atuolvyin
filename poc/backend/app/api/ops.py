from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import mask_phone, require_roles
from app.models.tenant import Tenant
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.tenant import TenantResponse

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
