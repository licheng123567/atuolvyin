"""v2.1 Task 3 — PC 管理员/督导查看坐席设备能力一览 (PRD § 8.4)。

GET /api/v1/admin/agent-devices?page=&page_size=&capability=&q=

返回 paginated 坐席设备列表。每个 (user_id, device_id) 取最新一条
device_capability_log（latest by id desc，等价于 detected_at desc 因为
detected_at 由 DB server_default=now()），并 join user_account / 当前
membership 拿姓名/角色。

权限：
  - admin / supervisor → 看本租户全部坐席（v2.1 暂不区分 supervisor 子组，
    沿用 admin_dashboard 现有「supervisor 看本租户全部」语义）
  - platform_superadmin → 看全租户
  - 其他角色 → 403

筛选：
  - capability=realtime|post_upload|incompatible（按 latest capability 过滤）
  - q=关键字（搜 user.name / device_id / model 模糊）

性能说明：subquery 取 MAX(id) GROUP BY (user_id, device_id)，PostgreSQL
对 (device_id) 索引 + (tenant_id, user_id, detected_at) 复合索引可高效命中。
当某租户活跃坐席 < 200、device_id 总量 < 1000 时，单次查询 < 50ms。
更大数据量需引入物化视图或 window function。
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.device_capability_log import DeviceCapabilityLog
from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount
from app.schemas.common import PaginatedResponse

router = APIRouter()

ALLOWED_ROLES = ("admin", "platform_superadmin", "supervisor")
PLATFORM_ROLES = ("platform_superadmin",)

_STATUS_LABEL = {
    "realtime": "实时可用",
    "post_upload": "事后上传",
    "incompatible": "录音不可用",
}

_VALID_CAPABILITIES = ("realtime", "post_upload", "incompatible")


class AgentDeviceItem(BaseModel):
    user_id: int
    user_name: str
    role: str
    device_id: str
    manufacturer: str | None
    model: str | None
    android_version: str | None
    rom_label: str | None
    latest_capability: Literal["realtime", "post_upload", "incompatible"]
    latest_self_check_at: datetime
    actual_recording_works: bool | None
    status_label: str  # 实时可用 / 事后上传 / 录音不可用


@router.get(
    "/agent-devices",
    response_model=PaginatedResponse[AgentDeviceItem],
)
def list_agent_devices(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ALLOWED_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    capability: str | None = Query(None),
    q: str | None = Query(None),
) -> PaginatedResponse[AgentDeviceItem]:
    tenant_id: int = int(payload.get("tenant_id") or 0)
    role: str = str(payload.get("role") or "")

    # 1. latest log subquery — 每个 (user_id, device_id) pair 取最大 id
    #    平台超管看全租户；其他角色限本租户
    latest_base = select(
        DeviceCapabilityLog.user_id.label("u_id"),
        DeviceCapabilityLog.device_id.label("d_id"),
        func.max(DeviceCapabilityLog.id).label("latest_id"),
    )
    if role not in PLATFORM_ROLES:
        latest_base = latest_base.where(DeviceCapabilityLog.tenant_id == tenant_id)
    latest_subq = latest_base.group_by(
        DeviceCapabilityLog.user_id,
        DeviceCapabilityLog.device_id,
    ).subquery()

    # 2. 主查询：join 拿 latest log 详情 + UserAccount + 当前租户 membership
    stmt = (
        select(DeviceCapabilityLog, UserAccount, UserTenantMembership)
        .join(latest_subq, DeviceCapabilityLog.id == latest_subq.c.latest_id)
        .join(UserAccount, UserAccount.id == DeviceCapabilityLog.user_id)
        .join(
            UserTenantMembership,
            (UserTenantMembership.user_id == UserAccount.id)
            & (UserTenantMembership.tenant_id == DeviceCapabilityLog.tenant_id)
            & (UserTenantMembership.is_active.is_(True)),
        )
    )

    if capability:
        if capability not in _VALID_CAPABILITIES:
            # 非法值直接返回空 — 不抛 422，避免前端单纯笔误中断
            return PaginatedResponse[AgentDeviceItem](
                items=[], total=0, page=page, page_size=page_size
            )
        stmt = stmt.where(DeviceCapabilityLog.capability == capability)
    if q:
        like_pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                UserAccount.name.ilike(like_pattern),
                DeviceCapabilityLog.device_id.ilike(like_pattern),
                DeviceCapabilityLog.model.ilike(like_pattern),
            )
        )

    # 3. 总数（基于过滤后子查询 count）
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(db.execute(count_stmt).scalar_one() or 0)

    # 4. 排序 + 分页
    stmt = (
        stmt.order_by(DeviceCapabilityLog.detected_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    rows = db.execute(stmt).all()
    items: list[AgentDeviceItem] = [
        AgentDeviceItem(
            user_id=user.id,
            user_name=user.name,
            role=membership.role,
            device_id=log.device_id,
            manufacturer=log.manufacturer,
            model=log.model,
            android_version=log.android_version,
            rom_label=log.rom_label,
            latest_capability=log.capability,  # type: ignore[arg-type]
            latest_self_check_at=log.detected_at,
            actual_recording_works=log.actual_recording_works,
            status_label=_STATUS_LABEL.get(log.capability, log.capability),
        )
        for log, user, membership in rows
    ]

    return PaginatedResponse[AgentDeviceItem](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
