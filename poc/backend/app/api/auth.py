from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone
from app.core.db import get_db
from app.core.security import create_access_token, verify_password
from app.models.active_session import ActiveSession
from app.models.tenant import Tenant, UserTenantMembership
from app.models.user import UserAccount
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.execute(
        select(UserAccount).where(
            UserAccount.phone_enc == encrypt_phone(body.phone),
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

    # MVP — seed 数据每个用户单 membership；多 membership 选择器属 v2.x 范畴 (PRD §5)
    membership = db.execute(
        select(UserTenantMembership)
        .where(
            UserTenantMembership.user_id == user.id,
            UserTenantMembership.is_active.is_(True),
        )
        .limit(1)
    ).scalar_one_or_none()

    tenant_id: int | None = None
    tenant_name: str | None = None
    role = "platform_superadmin"
    scope = "platform"

    if membership:
        tenant_id = membership.tenant_id
        role = membership.role
        scope = f"tenant:{membership.tenant_id}"
        tenant_name = db.execute(
            select(Tenant.name).where(Tenant.id == membership.tenant_id)
        ).scalar_one_or_none()

    user.last_login_at = datetime.now(UTC)

    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": tenant_id,
            "role": role,
            "scope": scope,
        }
    )

    # Sprint 15.1 — 多设备登录踢出 (PRD §11.5)
    # upsert (user_id, device_type) → 覆盖旧 token_hash → 旧 token 下次请求 401 ERR_SESSION_EVICTED
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stmt = pg_insert(ActiveSession).values(
        user_id=user.id,
        device_type=body.device_type,
        token_hash=token_hash,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "device_type"],
        set_={"token_hash": token_hash, "updated_at": datetime.now(UTC)},
    )
    db.execute(stmt)
    db.commit()

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        role=role,
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        scope=scope,
    )
