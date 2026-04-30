from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.device import DeviceProfile

router = APIRouter()

AGENT_ROLES = ("agent_internal", "agent_external")


class DeviceRegisterRequest(BaseModel):
    device_id: str
    brand: Optional[str] = None
    model: Optional[str] = None
    os_version: Optional[str] = None


class DeviceRegisterResponse(BaseModel):
    device_id: str
    user_id: int
    tenant_id: int
    brand: Optional[str] = None
    created_at: datetime


class SelfCheckRequest(BaseModel):
    device_id: str
    recording_dir_ok: bool
    recording_toggle_on: bool
    permissions_ok: bool


class SelfCheckResponse(BaseModel):
    can_call: bool


@router.post("/register", response_model=DeviceRegisterResponse, status_code=201)
def register_device(
    body: DeviceRegisterRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> DeviceRegisterResponse:
    user_id: int = payload["user_id"]
    tenant_id: int = payload["tenant_id"]

    stmt = (
        pg_insert(DeviceProfile)
        .values(
            device_id=body.device_id,
            user_id=user_id,
            tenant_id=tenant_id,
            brand=body.brand,
            model=body.model,
            os_version=body.os_version,
        )
        .on_conflict_do_update(
            index_elements=["device_id"],
            set_=dict(
                brand=body.brand,
                model=body.model,
                os_version=body.os_version,
                user_id=user_id,
                tenant_id=tenant_id,
            ),
        )
        .returning(
            DeviceProfile.id,
            DeviceProfile.device_id,
            DeviceProfile.user_id,
            DeviceProfile.tenant_id,
            DeviceProfile.brand,
            DeviceProfile.created_at,
        )
    )
    row = db.execute(stmt).fetchone()
    db.commit()

    return DeviceRegisterResponse(
        device_id=row.device_id,
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        brand=row.brand,
        created_at=row.created_at,
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

    device = db.execute(
        select(DeviceProfile).where(
            DeviceProfile.device_id == body.device_id,
            DeviceProfile.user_id == user_id,
            DeviceProfile.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_DEVICE_NOT_FOUND", "message": "设备未注册或不属于当前用户"},
        )

    is_healthy = body.recording_dir_ok and body.recording_toggle_on and body.permissions_ok
    device.is_healthy = is_healthy
    device.last_check_at = datetime.now(timezone.utc)
    db.commit()

    return SelfCheckResponse(can_call=is_healthy)


@router.get("/config")
def get_config(
    _payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
    device_id: Optional[str] = Query(None),
) -> dict:
    try:
        rows = db.execute(text("SELECT key, value FROM app_config")).fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception:
        return {}
