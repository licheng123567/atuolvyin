"""Sprint 15 — audit log helper.

Caller-managed transaction: log_audit() does NOT commit. Failures are swallowed
and logged so an audit-write error never breaks the parent business operation.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


def log_audit(
    db: Session,
    *,
    actor_user_id: int | None,
    actor_role: str | None,
    tenant_id: int | None,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Insert an AuditLog row inside the current transaction.

    The caller owns the commit. If the insert raises (e.g. unexpected schema),
    we catch and log — auditing must never break the actual business write.
    """
    try:
        entry = AuditLog(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            tenant_id=tenant_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
        )
        db.add(entry)
        db.flush()  # surface FK errors immediately, but stay in the parent tx
    except Exception:  # noqa: BLE001 — audit must never fail business action
        logger.exception(
            "audit log write failed (action=%s target=%s/%s)",
            action,
            target_type,
            target_id,
        )
