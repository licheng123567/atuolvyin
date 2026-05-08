"""v1.6 — 减免 offer 7 天有效期自动失效 sweep。

每小时扫一次 status 仍在审批 / 已批准但未执行的 offer，超过 expires_at 即标 expired。
follow heartbeat_cleanup_loop pattern in services/call_lifecycle.py.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.db import SessionLocal
from app.models.discount_offer import DiscountOffer

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"pending_supervisor", "pending_admin", "approved"}


def _sweep_once() -> int:
    """单次扫描，返回标记 expired 的数量。"""
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        rows = db.execute(
            select(DiscountOffer)
            .where(DiscountOffer.status.in_(ACTIVE_STATUSES))
            .where(DiscountOffer.expires_at < now)
        ).scalars().all()
        marked = 0
        for offer in rows:
            offer.status = "expired"
            trail = list(offer.audit_trail or [])
            trail.append({
                "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "actor": "系统",
                "action": "7 天有效期到期，自动失效",
            })
            offer.audit_trail = trail
            flag_modified(offer, "audit_trail")
            marked += 1
        if marked:
            db.commit()
        return marked
    except Exception:
        logger.exception("discount expiry sweep failed")
        db.rollback()
        return 0
    finally:
        db.close()


async def discount_expiry_loop(interval_sec: int = 3600) -> None:
    """每小时扫一次过期 offer。"""
    while True:
        try:
            n = await asyncio.to_thread(_sweep_once)
            if n:
                logger.info("discount expiry sweep: %d offers marked expired", n)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("discount expiry loop tick failed")
        await asyncio.sleep(interval_sec)
