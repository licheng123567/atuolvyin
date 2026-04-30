from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import create_access_token, verify_password
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    # phone_enc stores plaintext until Sprint 1 adds AES-256 encryption
    user = db.execute(
        select(UserAccount).where(
            UserAccount.phone_enc == body.phone,
            UserAccount.is_active.is_(True),
        )
    ).scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "ERR_INVALID_CREDENTIALS",
                "message": "手机号或密码错误",
            },
        )

    # Get first active membership (multi-tenant selector deferred to later sprint)
    membership = db.execute(
        select(UserTenantMembership)
        .where(
            UserTenantMembership.user_id == user.id,
            UserTenantMembership.is_active.is_(True),
        )
        .limit(1)
    ).scalar_one_or_none()

    tenant_id: Optional[int] = None
    role = "platform_superadmin"
    scope = "platform"

    if membership:
        tenant_id = membership.tenant_id
        role = membership.role
        scope = f"tenant:{membership.tenant_id}"

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": tenant_id,
            "role": role,
            "scope": scope,
        }
    )

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        role=role,
        tenant_id=tenant_id,
        scope=scope,
    )
