# notification channel modules: system / sms / wechat / dingtalk
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.notification import NotificationDeliveryLog


def log_delivery(
    db: Session,
    *,
    channel: str,
    tenant_id: int,
    user_id: int | None,
    event_type: str,
    severity: str,
    title: str,
    status: str,
    error: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Persist one delivery attempt; flush only (caller commits)."""
    try:
        db.add(
            NotificationDeliveryLog(
                tenant_id=tenant_id,
                user_id=user_id,
                channel=channel,
                event_type=event_type,
                severity=severity,
                status=status,
                title=title,
                error=error,
                payload=payload,
            )
        )
        db.flush()
    except Exception:  # noqa: BLE001 — log write must never break the dispatch
        import logging

        logging.getLogger(__name__).exception(
            "delivery log write failed (channel=%s event=%s)", channel, event_type
        )
