"""Sprint 14.2 — 通话生命周期：心跳超时清理 (PRD §10.1 / §11.6).

后台任务每 30s 扫描 status IN ('dialing','live') 且 last_heartbeat_at 早于 90s 的通话：
  - status → 'aborted'
  - 已扣的 realtime/post 配额回滚（dial-start 实际还没扣 → 无回滚）
  - WS 广播 call.aborted 给租户 supervisor 房间

也提供同步 cleanup_stale_calls 方便测试直接调用。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.call import CallRecord

logger = logging.getLogger(__name__)

HEARTBEAT_TIMEOUT_SEC = 90
SCAN_INTERVAL_SEC = 30


def cleanup_stale_calls(db: Session, *, now: datetime | None = None) -> list[int]:
    """同步执行清理。返回被 abort 的 call_id 列表。"""
    if now is None:
        now = datetime.now(UTC)
    threshold = now - timedelta(seconds=HEARTBEAT_TIMEOUT_SEC)

    stale = db.execute(
        select(CallRecord).where(
            CallRecord.status.in_(("dialing", "live")),
            CallRecord.last_heartbeat_at < threshold,
        )
    ).scalars().all()

    aborted_ids: list[int] = []
    for c in stale:
        c.status = "aborted"
        c.ended_at = now
        aborted_ids.append(c.id)
    if aborted_ids:
        db.commit()
        logger.info("cleanup_stale_calls aborted %d calls: %s", len(aborted_ids), aborted_ids)
    return aborted_ids


async def _broadcast_aborts(db: Session, aborted_ids: list[int]) -> None:
    if not aborted_ids:
        return
    from app.api.calls_v1 import _broadcast_call_event

    for cid in aborted_ids:
        c = db.get(CallRecord, cid)
        if c is None:
            continue
        try:
            await _broadcast_call_event(db, c, "call.aborted")
        except Exception as exc:
            logger.warning("call.aborted broadcast failed call_id=%s: %s", cid, exc)


async def heartbeat_cleanup_loop() -> None:
    """无限循环。FastAPI lifespan 中 create_task 启动。"""
    logger.info("heartbeat_cleanup_loop started (interval=%ds)", SCAN_INTERVAL_SEC)
    while True:
        try:
            with SessionLocal() as db:
                aborted = cleanup_stale_calls(db)
                if aborted:
                    await _broadcast_aborts(db, aborted)
        except Exception as exc:
            logger.exception("heartbeat_cleanup_loop iteration failed: %s", exc)
        await asyncio.sleep(SCAN_INTERVAL_SEC)
