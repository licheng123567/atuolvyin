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
        # v2.2 — 容忍输入法/复制粘贴带的空格、连字符、全角空格
        cleaned = v.strip().replace(" ", "").replace("　", "").replace("-", "")
        if not re.match(r"^1[3-9]\d{9}$", cleaned):
            raise ValueError("手机号格式无效，应为 11 位大陆手机号")
        return cleaned


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str
    role: str
    tenant_id: int | None
    tenant_name: str | None = None
    scope: str  # "platform" | "tenant:{id}" | "provider:{id}"
