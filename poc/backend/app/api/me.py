"""v1.5 S18.4 — 全角色个人中心。

端点：
    GET  /api/v1/me                          — 基本信息 + 安全状态
    PATCH /api/v1/me                         — 改姓名
    POST /api/v1/me/password                 — 设置/修改密码
    POST /api/v1/me/phone/change-request     — 旧手机收 OTP（双向校验第一步）
    POST /api/v1/me/phone/change-confirm     — 提交旧 OTP + 新手机 + 新 OTP
    POST /api/v1/me/email/bind               — 首次绑定邮箱（dev 模式直通）
    GET  /api/v1/me/login-history            — 最近登录记录（active_session）
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_phone, encrypt_phone, mask_phone
from app.core.db import get_db
from app.core.security import (
    get_password_hash,
    get_token_payload,
    verify_password,
)
from app.models.active_session import ActiveSession
from app.models.tenant import Tenant, UserTenantMembership
from app.models.user import UserAccount

from .auth_extras import _consume_otp, _create_otp

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────


class MeOut(BaseModel):
    id: int
    name: str
    role: str
    tenant_id: int | None
    tenant_name: str | None
    phone_masked: str
    email: str | None
    has_password: bool
    login_method: str  # phone / email / otp


class MeUpdateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


class PasswordUpdateIn(BaseModel):
    current_password: str | None = None  # 首次设置时可空
    new_password: str = Field(..., min_length=8, max_length=72)


class PhoneChangeRequestIn(BaseModel):
    """第一步：发送验证码到旧手机（当前手机号）"""

    pass


class PhoneChangeConfirmIn(BaseModel):
    old_otp: str = Field(..., min_length=4, max_length=8)
    new_phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    new_otp: str = Field(..., min_length=4, max_length=8)


class EmailBindIn(BaseModel):
    email: str = Field(..., max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class LoginHistoryItem(BaseModel):
    device_type: str
    created_at: datetime
    updated_at: datetime


class OkOut(BaseModel):
    status: Literal["ok"] = "ok"


class OtpSentOut(BaseModel):
    sent: bool = True
    expires_in: int = 300
    dev_code: str | None = None


# ─── Helpers ──────────────────────────────────────────────────


def _current_user(db: Session, payload: dict) -> UserAccount:
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_NO_USER", "message": "未登录"},
        )
    user = db.get(UserAccount, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_USER_NOT_FOUND", "message": "用户不存在"},
        )
    return user


def _decrypt_phone(enc: str) -> str:
    """从 phone_enc 反查明文手机号 — 用于 OTP 发送对比。"""
    return decrypt_phone(enc)


# ─── Endpoints ────────────────────────────────────────────────


@router.get("/me", response_model=MeOut)
def get_me(
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> MeOut:
    user = _current_user(db, payload)
    role = payload.get("role", "")
    tenant_id = payload.get("tenant_id")
    tenant_name: str | None = None
    if tenant_id:
        tenant_name = db.execute(
            select(Tenant.name).where(Tenant.id == int(tenant_id))
        ).scalar_one_or_none()
    # has_password 判断：bcrypt hash 总是 60 字符；占位 hash 也是 60 字符。
    # 用 login_method 标识用户是否走 OTP 优先（被 admin 创建未设密码）
    has_password = user.login_method != "otp"
    return MeOut(
        id=user.id,
        name=user.name,
        role=role,
        tenant_id=int(tenant_id) if tenant_id else None,
        tenant_name=tenant_name,
        phone_masked=mask_phone(user.phone_enc),
        email=user.email,
        has_password=has_password,
        login_method=user.login_method,
    )


@router.patch("/me", response_model=MeOut)
def update_me(
    body: MeUpdateIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> MeOut:
    user = _current_user(db, payload)
    user.name = body.name.strip()
    db.commit()
    return get_me(payload, db)


@router.post("/me/password", response_model=OkOut)
def set_password(
    body: PasswordUpdateIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> OkOut:
    """已有密码 → 必须验证当前密码；未设置（login_method='otp'）→ 直接设置。"""
    user = _current_user(db, payload)
    if user.login_method != "otp":
        # 已有密码，强制二次验证
        if not body.current_password or not verify_password(
            body.current_password, user.password_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ERR_WRONG_CURRENT_PASSWORD",
                    "message": "当前密码错误",
                },
            )
    user.password_hash = get_password_hash(body.new_password)
    user.login_method = "phone"  # 设置后偏好转 phone
    db.commit()
    return OkOut()


@router.post("/me/phone/change-request", response_model=OtpSentOut)
def phone_change_request(
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> OtpSentOut:
    """第一步：发送 OTP 到当前（旧）手机号。"""
    import os

    user = _current_user(db, payload)
    current_phone = _decrypt_phone(user.phone_enc)
    code = _create_otp(db, current_phone, "phone_change_old")
    dev_return = os.getenv("OTP_DEV_RETURN", "true").lower() == "true"
    return OtpSentOut(dev_code=code if dev_return else None)


@router.post("/me/phone/change-send-new", response_model=OtpSentOut)
def phone_change_send_new(
    body: dict[str, str],
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> OtpSentOut:
    """中间步：发送 OTP 到新手机号（验证旧 OTP 后才能调）。"""
    import os
    import re

    user = _current_user(db, payload)
    new_phone = body.get("new_phone", "").strip()
    if not re.match(r"^1[3-9]\d{9}$", new_phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_INVALID_PHONE", "message": "新手机号格式无效"},
        )
    # 防止换到已存在的手机号
    enc = encrypt_phone(new_phone)
    if enc == user.phone_enc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_SAME_PHONE", "message": "新手机号不能与当前一致"},
        )
    existing = db.execute(
        select(UserAccount).where(UserAccount.phone_enc == enc)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ERR_PHONE_TAKEN", "message": "手机号已被占用"},
        )
    code = _create_otp(db, new_phone, "phone_change_new")
    dev_return = os.getenv("OTP_DEV_RETURN", "true").lower() == "true"
    return OtpSentOut(dev_code=code if dev_return else None)


@router.post("/me/phone/change-confirm", response_model=OkOut)
def phone_change_confirm(
    body: PhoneChangeConfirmIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> OkOut:
    """提交旧 OTP + 新手机 + 新 OTP，双向校验通过后切换。"""
    user = _current_user(db, payload)
    current_phone = _decrypt_phone(user.phone_enc)
    if not _consume_otp(db, current_phone, body.old_otp, "phone_change_old"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_OLD_OTP", "message": "旧手机验证码错误或已过期"},
        )
    if not _consume_otp(db, body.new_phone, body.new_otp, "phone_change_new"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_NEW_OTP", "message": "新手机验证码错误或已过期"},
        )
    new_enc = encrypt_phone(body.new_phone)
    existing = db.execute(
        select(UserAccount).where(UserAccount.phone_enc == new_enc)
    ).scalar_one_or_none()
    if existing and existing.id != user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ERR_PHONE_TAKEN", "message": "手机号已被占用"},
        )
    user.phone_enc = new_enc
    db.commit()
    return OkOut()


@router.post("/me/email/bind", response_model=OkOut)
def email_bind(
    body: EmailBindIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> OkOut:
    """首次绑定 / 直接换绑邮箱（dev 模式直通；prod 应走激活链接，v1.5.1）。"""
    user = _current_user(db, payload)
    user.email = body.email
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ERR_EMAIL_TAKEN", "message": "邮箱已被占用"},
        ) from None
    return OkOut()


@router.get("/me/login-history", response_model=list[LoginHistoryItem])
def login_history(
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> list[LoginHistoryItem]:
    """最近 10 条登录会话记录（per-device-type，多设备踢出语义）。"""
    user = _current_user(db, payload)
    rows = db.execute(
        select(ActiveSession)
        .where(ActiveSession.user_id == user.id)
        .order_by(desc(ActiveSession.updated_at))
        .limit(10)
    ).scalars().all()
    return [
        LoginHistoryItem(
            device_type=r.device_type,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
