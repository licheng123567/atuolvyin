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


class InviteLinkRequest(BaseModel):
    role: str = "agent_external"
    quota: int = Field(20, ge=1, le=200)
    expire_days: int = Field(30, ge=1, le=90)
    access_hours: str | None = "09:00-18:00"


class InviteLinkResponse(BaseModel):
    token: str
    url: str
    expires_at: datetime


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
    password: str = Field(..., min_length=8, max_length=72)
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
