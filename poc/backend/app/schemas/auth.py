from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, field_validator


class LoginRequest(BaseModel):
    phone: str
    password: str
    # Sprint 15.1 — 多设备踢出：PC + App 互相独立计算，同类型新设备登录会踢旧设备
    device_type: Literal["pc", "app"] = "pc"

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
