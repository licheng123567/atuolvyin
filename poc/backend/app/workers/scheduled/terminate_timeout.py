"""Sprint 16.4 — Daily worker: auto-terminate contracts where the other party
did not confirm a termination request within 7 days (D2).

调用方式：
    python -m app.workers.scheduled.terminate_timeout

部署时由 systemd timer / Kubernetes CronJob / n8n 每日触发一次。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.api.provider_termination import CONFIRM_TIMEOUT_DAYS
from app.core.db import SessionLocal
from app.models.tenant import ProviderTenantContract
from app.services.audit import log_audit

logger = logging.getLogger("worker.terminate_timeout")


def run() -> int:
    """Auto-terminate contracts whose 7-day handshake window has expired.

    Returns the number of contracts auto-terminated.
    """
    cutoff = datetime.now(UTC) - timedelta(days=CONFIRM_TIMEOUT_DAYS)
    count = 0
    with SessionLocal() as db:
        rows = (
            db.execute(
                select(ProviderTenantContract).where(
                    ProviderTenantContract.termination_requested_at.is_not(None),
                    ProviderTenantContract.termination_requested_at < cutoff,
                    ProviderTenantContract.termination_confirmed_at.is_(None),
                    ProviderTenantContract.status != "terminated",
                )
            )
            .scalars()
            .all()
        )
        now = datetime.now(UTC)
        for c in rows:
            c.status = "terminated"
            c.terminated_at = now
            log_audit(
                db,
                actor_user_id=None,
                actor_role="system",
                tenant_id=c.tenant_id,
                action="provider.contract.auto_terminated",
                target_type="provider_tenant_contract",
                target_id=c.id,
                payload={
                    "provider_id": c.provider_id,
                    "requested_by": c.termination_requested_by,
                    "requested_at": c.termination_requested_at.isoformat()
                    if c.termination_requested_at
                    else None,
                    "reason": "timeout_7d",
                },
            )
            count += 1
        db.commit()
    logger.info("auto-terminated %d contracts past 7-day handshake window", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"auto-terminated {run()} contracts")
