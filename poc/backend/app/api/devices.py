from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db

router = APIRouter()


class SelfCheckIn(BaseModel):
    device_id: str
    brand: str | None = None
    model: str | None = None
    os_version: str | None = None
    recording_dir_ok: bool
    recording_toggle_on: bool
    permissions_ok: bool


@router.post("/self-check")
def self_check(payload: SelfCheckIn, db: Session = Depends(get_db)):
    ok = payload.recording_dir_ok and payload.recording_toggle_on and payload.permissions_ok
    db.execute(
        text("""
            INSERT INTO device(device_id, brand, model, os_version, last_self_check, self_check_ok)
            VALUES (:did, :brand, :model, :osv, :ts, :ok)
            ON CONFLICT (device_id) DO UPDATE SET
              brand=EXCLUDED.brand, model=EXCLUDED.model, os_version=EXCLUDED.os_version,
              last_self_check=EXCLUDED.last_self_check, self_check_ok=EXCLUDED.self_check_ok
        """),
        dict(
            did=payload.device_id,
            brand=payload.brand,
            model=payload.model,
            osv=payload.os_version,
            ts=datetime.utcnow(),
            ok=ok,
        ),
    )
    db.commit()
    return {"can_call": ok}


@router.get("/{device_id}/config")
def get_device_config(device_id: str, db: Session = Depends(get_db)):
    """运行时配置下发：按设备 ID 取，先取设备级覆盖，再取全局默认。
    APK 启动 + 自检后调用一次，缓存到本地；后台改了立即下发。
    """
    rows = (
        db.execute(
            text("""
        SELECT key, value FROM app_config
        WHERE scope = :did OR scope = 'global'
        ORDER BY scope = :did DESC      -- 设备级覆盖优先
    """),
            {"did": device_id},
        )
        .mappings()
        .all()
    )

    merged: dict = {}
    for r in rows:
        merged.setdefault(r["key"], r["value"])
    return merged
