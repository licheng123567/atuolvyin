from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    role: str
    supervisor_id: int | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone_masked: str  # 138****1234，service 层计算
    role: str
    is_active: bool
    created_at: datetime


class UserMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: str
    tenant_id: int | None
    scope: str


class UserCreateByAdminRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    # v1.4 方案 A — 不强制设置初始密码，员工首次登录走手机+OTP；
    # 若 admin 想给一个初始密码也允许（≥ 8 位）。
    password: str | None = Field(None, min_length=8, max_length=72)
    role: str = Field(
        ...,
        pattern=r"^(supervisor|agent_internal|legal|workorder|project_manager_property)$",
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class UserListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone_masked: str
    role: str
    is_active: bool
    created_at: datetime
