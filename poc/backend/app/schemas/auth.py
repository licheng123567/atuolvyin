from __future__ import annotations

import re

from pydantic import BaseModel, field_validator


class LoginRequest(BaseModel):
    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式无效，应为 11 位大陆手机号")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str
    role: str
    tenant_id: int | None
    scope: str  # "platform" | "tenant:{id}" | "provider:{id}"
