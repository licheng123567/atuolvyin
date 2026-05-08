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
        pattern=r"^(supervisor|agent_internal|legal|workorder|coordinator|project_manager_property)$",
    )
    # v1.5.6 — 一人多角色：可选额外角色（默认空，与 role 字段构成完整 membership 集）
    extra_roles: list[str] = Field(default_factory=list)

    model_config = ConfigDict(str_strip_whitespace=True)


class UserListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone_masked: str
    role: str  # 主角色（兼岗时为第一个）
    is_active: bool
    created_at: datetime
    # v1.5.5 — 创建后立即返回首登 OTP（dev 模式）+ 完整手机号（仅创建/issue-otp 端点回传）
    initial_otp: str | None = None
    phone_full: str | None = None
    email: str | None = None
    last_login_at: datetime | None = None
    login_method: str | None = None
    # v1.5.6 — 一人多角色：本租户内所有 active membership 的 role 列表
    all_roles: list[str] | None = None


class UserUpdateByAdminRequest(BaseModel):
    """v1.5.5 — admin 编辑员工。手机号不在本端点改（走 issue-otp 重发或员工本人 /me）。"""

    name: str | None = Field(None, min_length=1, max_length=50)
    role: str | None = Field(
        None,
        pattern=r"^(supervisor|agent_internal|legal|workorder|coordinator|project_manager_property)$",
    )
    # v1.5.6 — 一人多角色：完整覆盖该用户在本租户的 membership 列表
    # 传入则按列表 reconcile（新增/失活）；不传则只更新单 role / 不动 membership
    roles: list[str] | None = None
    email: str | None = Field(None, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    is_active: bool | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class UserOtpIssueOut(BaseModel):
    phone_masked: str
    phone_full: str | None = None  # dev 模式回传，prod None
    otp: str | None = None  # dev 模式回传，prod None
