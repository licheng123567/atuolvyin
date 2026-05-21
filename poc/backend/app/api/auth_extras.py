"""v1.4 S17.4 — 登录方式扩展：信用代码 + OTP 验证码。

设计文档：docs/account-architecture.md（v1.5 完整推进，v1.4 先落 MVP）

端点：
    POST /api/v1/auth/login-by-credit-code  — tenant credit_code + admin password
    POST /api/v1/auth/otp/send              — 发送 OTP 到手机（dev 模式直接返回 code）
    POST /api/v1/auth/otp/verify            — OTP 登录
    POST /api/v1/auth/password-reset/request — 发送密码重置 OTP
    POST /api/v1/auth/password-reset/confirm — 用 OTP 重设密码
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone
from app.core.db import get_db
from app.core.identity import resolve_identity
from app.core.security import (
    create_access_token,
    get_password_hash,
    get_token_payload,
    verify_password,
)
from app.models.active_session import ActiveSession
from app.models.login_otp import LoginOtp
from app.models.tenant import Tenant, UserTenantMembership
from app.models.user import UserAccount
from app.schemas.auth import TokenResponse
from app.services.sms_center import send_otp_sms

logger = logging.getLogger(__name__)

router = APIRouter()

OTP_TTL_SECONDS = 5 * 60
OTP_RATE_LIMIT_SECONDS = 60
OTP_DEV_RETURN = os.getenv("OTP_DEV_RETURN", "true").lower() == "true"
ADMIN_LIKE_ROLES = {"admin"}


def _phone_validator(v: str) -> str:
    import re

    if not re.match(r"^1[3-9]\d{9}$", v):
        raise ValueError("手机号格式无效")
    return v


def _credit_code_validator(v: str) -> str:
    # 18 位统一社会信用代码（数字 + 大写字母 0-9 A-Z 但不含 I/O/Z/S/V，简化为字母数字）
    import re

    if not re.match(r"^[0-9A-Z]{18}$", v):
        raise ValueError("社会信用代码格式无效（应为 18 位大写字母数字）")
    return v


# ─── Schemas ──────────────────────────────────────────────────


class CreditCodeLoginIn(BaseModel):
    credit_code: str = Field(..., min_length=18, max_length=18)
    password: str
    device_type: str = "pc"

    @field_validator("credit_code")
    @classmethod
    def _validate_cc(cls, v: str) -> str:
        return _credit_code_validator(v)


class UniversalLoginIn(BaseModel):
    """v1.4 — 用户名 + 密码统一入口。account 自动识别为：
    - 11 位数字 → 手机号
    - 18 位大写字母数字 → 统一社会信用代码
    - 含 @ → 邮箱
    """

    account: str = Field(..., min_length=1, max_length=120)
    password: str
    device_type: str = "pc"


class OtpSendIn(BaseModel):
    phone: str
    purpose: str = "login"  # login / password_reset

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        return _phone_validator(v)


class OtpVerifyIn(BaseModel):
    phone: str
    code: str = Field(..., min_length=4, max_length=8)
    device_type: str = "pc"

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        return _phone_validator(v)


class OtpSendOut(BaseModel):
    sent: bool = True
    expires_in: int = OTP_TTL_SECONDS
    # dev mode helper — production environment 必须把 OTP_DEV_RETURN=false
    dev_code: str | None = None


class PasswordResetRequestIn(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        return _phone_validator(v)


class PasswordResetConfirmIn(BaseModel):
    phone: str
    code: str = Field(..., min_length=4, max_length=8)
    new_password: str = Field(..., min_length=6, max_length=64)

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        return _phone_validator(v)


# ─── Helpers ──────────────────────────────────────────────────


def _issue_token(db: Session, user: UserAccount, device_type: str) -> TokenResponse:
    claims = resolve_identity(db, user)

    user.last_login_at = datetime.now(UTC)
    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": claims.tenant_id,
            "role": claims.role,
            "scope": claims.scope,
            "provider_id": claims.provider_id,
        }
    )
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stmt = pg_insert(ActiveSession).values(
        user_id=user.id, device_type=device_type, token_hash=token_hash
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
        role=claims.role,
        tenant_id=claims.tenant_id,
        tenant_name=claims.tenant_name,
        scope=claims.scope,
    )


def _generate_otp() -> str:
    # 6-digit
    return f"{secrets.randbelow(1_000_000):06d}"


def _create_otp(db: Session, phone: str, purpose: str) -> str:
    """Insert a fresh OTP (rate-limited). Returns the code (caller decides
    whether to expose it back to client)."""
    enc = encrypt_phone(phone)
    # rate-limit: latest non-consumed OTP issued within last 60s → reject
    recent = db.execute(
        select(LoginOtp)
        .where(
            LoginOtp.phone_enc == enc,
            LoginOtp.purpose == purpose,
            LoginOtp.created_at >= datetime.now(UTC) - timedelta(seconds=OTP_RATE_LIMIT_SECONDS),
        )
        .order_by(LoginOtp.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if recent is not None and recent.consumed_at is None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "ERR_OTP_RATE_LIMIT",
                "message": "验证码请求过于频繁，请 60 秒后再试",
            },
        )
    code = _generate_otp()
    db.add(
        LoginOtp(
            phone_enc=enc,
            code=code,
            purpose=purpose,
            expires_at=datetime.now(UTC) + timedelta(seconds=OTP_TTL_SECONDS),
        )
    )
    db.commit()
    return code


def _consume_otp(db: Session, phone: str, code: str, purpose: str) -> bool:
    enc = encrypt_phone(phone)
    row = db.execute(
        select(LoginOtp)
        .where(
            LoginOtp.phone_enc == enc,
            LoginOtp.code == code,
            LoginOtp.purpose == purpose,
            LoginOtp.consumed_at.is_(None),
            LoginOtp.expires_at > datetime.now(UTC),
        )
        .order_by(LoginOtp.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return False
    row.consumed_at = datetime.now(UTC)
    db.commit()
    return True


# v1.5.5 — 邮箱 OTP（复用 LoginOtp 表，phone_enc 列存 email 明文 + "email:" 前缀）
def _email_key(email: str) -> str:
    return f"email:{email.strip().lower()}"


def _create_otp_email(db: Session, email: str, purpose: str) -> str:
    """生成邮箱 OTP，用 email_send dispatcher 发送（dev console 直接打印）。
    返回 code 供 dev 模式回传给前端。"""
    from app.services.email_send import send_email

    key = _email_key(email)
    recent = db.execute(
        select(LoginOtp)
        .where(
            LoginOtp.phone_enc == key,
            LoginOtp.purpose == purpose,
            LoginOtp.created_at >= datetime.now(UTC) - timedelta(seconds=OTP_RATE_LIMIT_SECONDS),
        )
        .order_by(LoginOtp.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if recent is not None and recent.consumed_at is None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "ERR_OTP_RATE_LIMIT",
                "message": "验证码请求过于频繁，请 60 秒后再试",
            },
        )
    code = _generate_otp()
    db.add(
        LoginOtp(
            phone_enc=key,
            code=code,
            purpose=purpose,
            expires_at=datetime.now(UTC) + timedelta(seconds=OTP_TTL_SECONDS),
        )
    )
    db.commit()
    send_email(
        to=email,
        subject="【有证慧催】邮箱验证码",
        body=f"您的验证码：{code}\n5 分钟内有效，请勿告知他人。",
    )
    return code


def _consume_otp_email(db: Session, email: str, code: str, purpose: str) -> bool:
    key = _email_key(email)
    row = db.execute(
        select(LoginOtp)
        .where(
            LoginOtp.phone_enc == key,
            LoginOtp.code == code,
            LoginOtp.purpose == purpose,
            LoginOtp.consumed_at.is_(None),
            LoginOtp.expires_at > datetime.now(UTC),
        )
        .order_by(LoginOtp.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return False
    row.consumed_at = datetime.now(UTC)
    db.commit()
    return True


def _mask_otp_phone(p: str) -> str:
    """脱敏手机号，仅用于日志输出。"""
    if len(p) >= 11:
        return p[:3] + "****" + p[-4:]
    return "***"


def _send_otp_and_respond(db: Session, phone: str, code: str) -> OtpSendOut:
    """发 OTP 短信并构造响应。短信失败 → 403 ERR_SMS_SEND_FAILED。"""
    result = send_otp_sms(db, phone=phone, code=code, ttl_minutes=OTP_TTL_SECONDS // 60)
    if not result.ok:
        logger.warning("OTP 短信发送失败 phone=%s reason=%s", _mask_otp_phone(phone), result.error)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_SMS_SEND_FAILED", "message": "验证码短信发送失败，请稍后重试"},
        )
    return OtpSendOut(
        sent=True, expires_in=OTP_TTL_SECONDS, dev_code=code if OTP_DEV_RETURN else None
    )


# ─── Endpoints ────────────────────────────────────────────────


@router.post("/login-universal", response_model=TokenResponse)
def login_universal(body: UniversalLoginIn, db: Session = Depends(get_db)) -> TokenResponse:
    """统一账号登录入口（v1.4）。account 自动识别为手机号/信用代码/邮箱。"""
    import re

    account = body.account.strip()
    user: UserAccount | None = None

    if re.match(r"^1[3-9]\d{9}$", account):
        # 手机号登录
        user = db.execute(
            select(UserAccount).where(
                UserAccount.phone_enc == encrypt_phone(account),
                UserAccount.is_active.is_(True),
            )
        ).scalar_one_or_none()
    elif re.match(r"^[0-9A-Z]{18}$", account.upper()):
        # 统一社会信用代码 → 找该 tenant 的 admin
        cc = account.upper()
        tenant = db.execute(
            select(Tenant).where(Tenant.credit_code == cc, Tenant.is_active.is_(True))
        ).scalar_one_or_none()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "ERR_INVALID_ACCOUNT",
                    "message": "账号或密码错误",
                },
            )
        membership = (
            db.execute(
                select(UserTenantMembership).where(
                    UserTenantMembership.tenant_id == tenant.id,
                    UserTenantMembership.role.in_(ADMIN_LIKE_ROLES),
                    UserTenantMembership.is_active.is_(True),
                )
            )
            .scalars()
            .first()
        )
        if membership:
            user = db.get(UserAccount, membership.user_id)
    elif "@" in account:
        # 邮箱登录
        user = db.execute(
            select(UserAccount).where(
                UserAccount.email == account.lower(),
                UserAccount.is_active.is_(True),
            )
        ).scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_CREDENTIALS", "message": "账号或密码错误"},
        )
    return _issue_token(db, user, body.device_type)


@router.post("/login-by-credit-code", response_model=TokenResponse)
def login_by_credit_code(body: CreditCodeLoginIn, db: Session = Depends(get_db)) -> TokenResponse:
    """组织 admin 用社会信用代码登录（先查 tenant，再找该 tenant 的 admin 用户）。"""
    tenant = db.execute(
        select(Tenant).where(Tenant.credit_code == body.credit_code, Tenant.is_active.is_(True))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "ERR_INVALID_CREDIT_CODE",
                "message": "社会信用代码无效或租户已停用",
            },
        )
    # 找 tenant 下的第一个 admin 用户（MVP 假设 1 admin / tenant）
    membership = (
        db.execute(
            select(UserTenantMembership).where(
                UserTenantMembership.tenant_id == tenant.id,
                UserTenantMembership.role.in_(ADMIN_LIKE_ROLES),
                UserTenantMembership.is_active.is_(True),
            )
        )
        .scalars()
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "ERR_NO_ADMIN",
                "message": "该租户暂未配置管理员账号，请联系平台",
            },
        )
    user = db.get(UserAccount, membership.user_id)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_CREDENTIALS", "message": "密码错误"},
        )
    return _issue_token(db, user, body.device_type)


@router.post("/otp/send", response_model=OtpSendOut)
def otp_send(body: OtpSendIn, db: Session = Depends(get_db)) -> OtpSendOut:
    code = _create_otp(db, body.phone, body.purpose)
    return _send_otp_and_respond(db, body.phone, code)


@router.post("/otp/verify", response_model=TokenResponse)
def otp_verify(body: OtpVerifyIn, db: Session = Depends(get_db)) -> TokenResponse:
    if not _consume_otp(db, body.phone, body.code, "login"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_OTP", "message": "验证码错误或已过期"},
        )
    user = db.execute(
        select(UserAccount).where(
            UserAccount.phone_enc == encrypt_phone(body.phone),
            UserAccount.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_USER_NOT_FOUND", "message": "用户不存在或已停用"},
        )
    return _issue_token(db, user, body.device_type)


@router.post("/password-reset/request", response_model=OtpSendOut)
def password_reset_request(
    body: PasswordResetRequestIn, db: Session = Depends(get_db)
) -> OtpSendOut:
    user = db.execute(
        select(UserAccount).where(
            UserAccount.phone_enc == encrypt_phone(body.phone),
            UserAccount.is_active.is_(True),
        )
    ).scalar_one_or_none()
    # 用户不存在仍假装成功（防爆破探测）
    if user:
        code = _create_otp(db, body.phone, "password_reset")
        return _send_otp_and_respond(db, body.phone, code)
    return OtpSendOut(sent=True, expires_in=OTP_TTL_SECONDS)


@router.post("/password-reset/confirm")
def password_reset_confirm(
    body: PasswordResetConfirmIn, db: Session = Depends(get_db)
) -> dict[str, str]:
    if not _consume_otp(db, body.phone, body.code, "password_reset"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_OTP", "message": "验证码错误或已过期"},
        )
    user = db.execute(
        select(UserAccount).where(
            UserAccount.phone_enc == encrypt_phone(body.phone),
            UserAccount.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_USER_NOT_FOUND", "message": "用户不存在"},
        )
    user.password_hash = get_password_hash(body.new_password)
    db.commit()
    return {"status": "ok"}


# v1.5.6 — 多 membership 切换：拿目标 membership_id 重新签 token
class SelectMembershipIn(BaseModel):
    membership_id: int
    device_type: str = "pc"


@router.post("/select-membership", response_model=TokenResponse)
def select_membership(
    body: SelectMembershipIn,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_token_payload),
) -> TokenResponse:
    user_id = int(payload.get("user_id") or 0)
    membership = db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.id == body.membership_id,
            UserTenantMembership.user_id == user_id,
            UserTenantMembership.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_MEMBERSHIP_NOT_FOUND", "message": "未找到该角色，可能已被禁用"},
        )

    user = db.get(UserAccount, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_USER_NOT_FOUND", "message": "用户不存在"},
        )

    claims = resolve_identity(db, user, membership=membership)

    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": claims.tenant_id,
            "role": claims.role,
            "scope": claims.scope,
            "provider_id": claims.provider_id,
        }
    )
    # 同步 active_session（按 device_type）
    import hashlib

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stmt = (
        pg_insert(ActiveSession)
        .values(
            user_id=user.id,
            device_type=body.device_type,
            token_hash=token_hash,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "device_type"],
            set_={"token_hash": token_hash, "updated_at": datetime.now(UTC)},
        )
    )
    db.execute(stmt)
    db.commit()

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        role=claims.role,
        tenant_id=claims.tenant_id,
        tenant_name=claims.tenant_name,
        scope=claims.scope,
    )
