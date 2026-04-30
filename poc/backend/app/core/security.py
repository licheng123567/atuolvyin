from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db

if TYPE_CHECKING:
    from app.models.user import UserAccount

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    payload: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = payload.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expires_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token invalid or expired"},
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_token_payload(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> dict:
    return decode_access_token(token)


async def get_current_user(
    payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> "UserAccount":
    from app.models.user import UserAccount  # avoid circular at module level

    user_id: Optional[int] = payload.get("user_id")
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
