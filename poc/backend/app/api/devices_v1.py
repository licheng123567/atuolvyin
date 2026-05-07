from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.device import DeviceProfile

router = APIRouter()

AGENT_ROLES = ("agent_internal", "agent_external")


class DeviceRegisterRequest(BaseModel):
    device_id: str
    brand: str | None = None
    model: str | None = None
    os_version: str | None = None
    push_reg_id: str | None = None
    push_provider: str | None = None  # 'xiaomi' | 'huawei' | 'google'


class DeviceRegisterResponse(BaseModel):
    device_id: str
    user_id: int
    tenant_id: int
    brand: str | None = None
    created_at: datetime
    push_reg_id_set: bool = False


class SelfCheckRequest(BaseModel):
    device_id: str
    recording_dir_ok: bool
    recording_toggle_on: bool
    permissions_ok: bool


class SelfCheckResponse(BaseModel):
    can_call: bool
    fail_reasons: list[str] = []  # v1.6 — recording_dir / recording_toggle / permissions


class PushRegPatchRequest(BaseModel):
    device_id: str
    push_reg_id: str
    push_provider: str  # 'xiaomi' | 'huawei' | 'google'


class PushRegPatchResponse(BaseModel):
    device_id: str
    push_reg_id_set: bool


@router.post("/register", response_model=DeviceRegisterResponse, status_code=201)
def register_device(
    body: DeviceRegisterRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> DeviceRegisterResponse:
    user_id: int = payload["user_id"]
    tenant_id: int = payload["tenant_id"]

    insert_stmt = pg_insert(DeviceProfile).values(
        device_id=body.device_id,
        user_id=user_id,
        tenant_id=tenant_id,
        brand=body.brand,
        model=body.model,
        os_version=body.os_version,
        push_reg_id=body.push_reg_id,
        push_provider=body.push_provider,
    )
    # On conflict: update fields. For push_reg_id / push_provider, only overwrite
    # when the new payload provides a non-null value — otherwise preserve the
    # previously stored value via COALESCE(EXCLUDED.x, table.x).
    excluded = insert_stmt.excluded
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=["device_id"],
        set_=dict(
            brand=body.brand,
            model=body.model,
            os_version=body.os_version,
            user_id=user_id,
            tenant_id=tenant_id,
            push_reg_id=func.coalesce(excluded.push_reg_id, DeviceProfile.push_reg_id),
            push_provider=func.coalesce(excluded.push_provider, DeviceProfile.push_provider),
        ),
    ).returning(
        DeviceProfile.id,
        DeviceProfile.device_id,
        DeviceProfile.user_id,
        DeviceProfile.tenant_id,
        DeviceProfile.brand,
        DeviceProfile.created_at,
        DeviceProfile.push_reg_id,
    )
    row = db.execute(stmt).fetchone()
    db.commit()

    return DeviceRegisterResponse(
        device_id=row.device_id,
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        brand=row.brand,
        created_at=row.created_at,
        push_reg_id_set=bool(row.push_reg_id),
    )


@router.post("/self-check", response_model=SelfCheckResponse)
def self_check(
    body: SelfCheckRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SelfCheckResponse:
    user_id: int = payload["user_id"]
    tenant_id: int = payload["tenant_id"]

    # 区分「设备未注册」与「属他人/他租户」两类失败 — 前端给出不同引导
    device = db.execute(
        select(DeviceProfile).where(DeviceProfile.device_id == body.device_id)
    ).scalar_one_or_none()
    if device is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ERR_DEVICE_NOT_REGISTERED",
                "message": "设备尚未注册，请先完成登录后的设备注册",
            },
        )
    if device.user_id != user_id or device.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ERR_DEVICE_OWNED_BY_OTHER",
                "message": "本设备已绑定其他账号，请改账号或联系管理员",
            },
        )

    fail_reasons: list[str] = []
    if not body.recording_dir_ok:
        fail_reasons.append("recording_dir")
    if not body.recording_toggle_on:
        fail_reasons.append("recording_toggle")
    if not body.permissions_ok:
        fail_reasons.append("permissions")

    is_healthy = not fail_reasons
    device.is_healthy = is_healthy
    device.last_check_at = datetime.now(UTC)
    db.commit()

    return SelfCheckResponse(can_call=is_healthy, fail_reasons=fail_reasons)


@router.patch("/push-reg", response_model=PushRegPatchResponse)
def patch_push_reg(
    body: PushRegPatchRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> PushRegPatchResponse:
    """v1.6 — push 通道单独注册回调入口。

    要求 device 已经通过 /devices/register 创建（一般在登录后由 App 触发）。
    push 回调晚于登录到达：仅 patch push_reg_id/push_provider，不创建 row、
    不改 brand/model 等字段，避免跨账号的 push 回调污染设备绑定。
    """
    user_id: int = payload["user_id"]
    tenant_id: int = payload["tenant_id"]

    device = db.execute(
        select(DeviceProfile).where(DeviceProfile.device_id == body.device_id)
    ).scalar_one_or_none()
    if device is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ERR_DEVICE_NOT_REGISTERED",
                "message": "设备尚未注册，请先登录完成主注册流程",
            },
        )
    if device.user_id != user_id or device.tenant_id != tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ERR_DEVICE_OWNED_BY_OTHER",
                "message": "本设备已绑定其他账号",
            },
        )

    device.push_reg_id = body.push_reg_id
    device.push_provider = body.push_provider
    db.commit()

    return PushRegPatchResponse(
        device_id=device.device_id,
        push_reg_id_set=bool(device.push_reg_id),
    )


@router.get("/config")
def get_config(
    _payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
    device_id: str | None = Query(None),
) -> dict:
    try:
        rows = db.execute(text("SELECT key, value FROM app_config")).fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception:
        return {}
