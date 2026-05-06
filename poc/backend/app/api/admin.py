from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pydantic import BaseModel

from app.core.crypto import encrypt_phone
from app.core.db import get_db
from app.core.security import (
    get_password_hash,
    get_token_payload,
    mask_phone,
    require_roles,
)
from app.models.device import DeviceProfile
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.user import (
    InviteLinkRequest,
    InviteLinkResponse,
    UserCreateByAdminRequest,
    UserListResponse,
)


class AdminDeviceItem(BaseModel):
    device_id: str
    user_id: int
    brand: str | None = None
    model: str | None = None
    os_version: str | None = None
    push_reg_id_set: bool
    push_provider: str | None = None
    is_healthy: bool
    last_check_at: datetime | None = None
    created_at: datetime

router = APIRouter()

ADMIN_ROLES = ("admin",)


def _user_to_response(user: UserAccount, role: str) -> UserListResponse:
    return UserListResponse(
        id=user.id,
        name=user.name,
        phone_masked=mask_phone(user.phone_enc),
        role=role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("/users", response_model=PaginatedResponse[UserListResponse])
async def list_users(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[UserListResponse]:
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    stmt = (
        select(UserAccount, UserTenantMembership.role)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.is_active.is_(True),
        )
    )
    if q:
        stmt = stmt.where(UserAccount.name.ilike(f"%{q}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(count_stmt).scalar_one()

    rows = db.execute(
        stmt.order_by(UserAccount.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedResponse(
        items=[_user_to_response(user, role) for user, role in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/users", response_model=UserListResponse, status_code=201)
async def create_user(
    body: UserCreateByAdminRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> UserListResponse:
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    new_user = UserAccount(
        phone_enc=encrypt_phone(body.phone),
        name=body.name,
        password_hash=get_password_hash(body.password),
        is_active=True,
    )
    db.add(new_user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"code": "ERR_DUPLICATE_PHONE", "message": "手机号已被注册"},
        ) from None

    membership = UserTenantMembership(
        user_id=new_user.id,
        tenant_id=tenant_id,
        role=body.role,
        source_type="INTERNAL",
        is_active=True,
    )
    db.add(membership)
    db.commit()
    db.refresh(new_user)
    return _user_to_response(new_user, body.role)


@router.post("/users/invite", response_model=InviteLinkResponse, status_code=201)
async def generate_invite_link(
    body: InviteLinkRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
) -> InviteLinkResponse:
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=body.expire_days)
    # Invite token storage deferred to Sprint 2 (need invite_token table)
    return InviteLinkResponse(
        token=token,
        url=f"/register?token={token}",
        expires_at=expires_at,
    )


@router.get("/devices", response_model=list[AdminDeviceItem])
async def list_devices(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    user_id: int | None = Query(None),
) -> list[AdminDeviceItem]:
    """Sprint 12 — admin troubleshooting: see whether a user's device is push-registered.

    The raw push_reg_id is never exposed; callers see only push_reg_id_set.
    Scoped to the caller's tenant.
    """
    tenant_id: int | None = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    stmt = select(DeviceProfile).where(DeviceProfile.tenant_id == tenant_id)
    if user_id is not None:
        stmt = stmt.where(DeviceProfile.user_id == user_id)
    stmt = stmt.order_by(DeviceProfile.id.desc())

    devices = db.execute(stmt).scalars().all()
    return [
        AdminDeviceItem(
            device_id=d.device_id,
            user_id=d.user_id,
            brand=d.brand,
            model=d.model,
            os_version=d.os_version,
            push_reg_id_set=bool(d.push_reg_id),
            push_provider=d.push_provider,
            is_healthy=d.is_healthy,
            last_check_at=d.last_check_at,
            created_at=d.created_at,
        )
        for d in devices
    ]
