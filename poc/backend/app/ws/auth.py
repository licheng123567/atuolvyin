# poc/backend/app/ws/auth.py
"""JWT validation for WebSocket query-string token."""
from __future__ import annotations

from typing import Optional

from jose import JWTError, jwt

from app.core.config import settings


def decode_ws_token(token: str) -> Optional[dict]:
    """Return JWT payload dict or None if invalid."""
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None
    if "user_id" not in payload or "tenant_id" not in payload:
        return None
    return payload
