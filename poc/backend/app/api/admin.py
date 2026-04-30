from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone
from app.core.db import get_db
from app.core.security import (
    get_current_user,
    get_password_hash,
    get_token_payload,
    mask_phone,
    require_roles,
)
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse
from app.schemas.user import InviteLinkRequest, InviteLinkResponse, UserCreateByAdminRequest, UserListResponse

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
    q: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[UserListResponse]:
    tenant_id: Optional[int] = payload.get("tenant_id")
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
    tenant_id: Optional[int] = payload.get("tenant_id")
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
        )

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
    tenant_id: Optional[int] = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NO_TENANT", "message": "此端点需要租户上下文"},
        )

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=body.expire_days)
    # Invite token storage deferred to Sprint 2 (need invite_token table)
    return InviteLinkResponse(
        token=token,
        url=f"/register?token={token}",
        expires_at=expires_at,
    )
