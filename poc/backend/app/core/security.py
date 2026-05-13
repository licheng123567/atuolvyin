from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db

if TYPE_CHECKING:
    from app.models.user import UserAccount

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_password_hash(password: str) -> str:
    """Hash a password with bcrypt (cost factor 12 default).

    v1.7.0 — replaces passlib.CryptContext (passlib 1.7.4 is archived and
    incompatible with bcrypt >= 5.x). bcrypt's 72-byte input limit is
    enforced upstream by Pydantic schemas (`max_length=72`).
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash. Pre-existing hashes
    written by passlib are standard bcrypt strings and verify identically."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        # Malformed hash → treat as mismatch (no info leak)
        return False


def create_access_token(
    payload: dict,
    expires_delta: timedelta | None = None,
) -> str:
    import uuid

    to_encode = payload.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.jwt_expires_minutes))
    to_encode["exp"] = expire
    # Sprint 15.1 — jti 保证每个 token 唯一（多设备踢出 hash 比对依赖）
    to_encode.setdefault("jti", uuid.uuid4().hex)
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token invalid or expired"},
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


async def get_token_payload(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> dict:
    payload = decode_access_token(token)
    # Sprint 15.1 — 多设备踢出：验证 token_hash 是否仍是该用户该设备类型的最新会话
    # 若该 user_id 完全没有 active_session 记录（未走过 v1.4 login，老 token），
    # 视为合法以保持向后兼容；只有当存在记录但 hash 不匹配时才 401。
    user_id = payload.get("user_id")
    if user_id and db is not None:
        import hashlib

        from sqlalchemy import select

        from app.models.active_session import ActiveSession

        rows = (
            db.execute(select(ActiveSession.token_hash).where(ActiveSession.user_id == user_id))
            .scalars()
            .all()
        )
        if rows:  # 有过 v1.4 登录记录
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            if token_hash not in rows:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "code": "ERR_SESSION_EVICTED",
                        "message": "您的账号已在其他设备登录",
                    },
                    headers={"WWW-Authenticate": "Bearer"},
                )
    return payload


async def get_current_user(
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> "UserAccount":
    from app.models.user import UserAccount  # avoid circular at module level

    user_id: int | None = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Invalid token payload"},
        )
    user = db.get(UserAccount, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_USER_INACTIVE", "message": "User not found or inactive"},
        )
    return user


def require_roles(*roles: str):
    """Usage: user: UserAccount = Depends(require_roles("admin", "supervisor"))"""

    async def _check(
        payload: Annotated[dict, Depends(get_token_payload)],
        user: Annotated["UserAccount", Depends(get_current_user)],
    ) -> "UserAccount":
        role: str = payload.get("role", "")
        if role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ERR_FORBIDDEN",
                    "message": f"Role '{role}' is not permitted for this endpoint",
                },
            )
        return user

    return _check


def mask_phone(phone_enc: str) -> str:
    """Decrypt AES-256 ciphertext and return masked form like 138****1234."""
    from app.core.crypto import mask_phone as _mask  # avoid circular at module level

    return _mask(phone_enc)
