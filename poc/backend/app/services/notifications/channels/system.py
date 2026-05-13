"""站内信渠道 — 写 notification 表 (Sprint 15.4)。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.notification import Notification

from . import log_delivery


def send(
    db: Session,
    *,
    tenant_id: int,
    event_type: str,
    severity: str,
    title: str,
    body: str,
    recipient_user_ids: list[int],
    payload: dict[str, Any] | None,
) -> None:
    for user_id in recipient_user_ids:
        db.add(
            Notification(
                tenant_id=tenant_id,
                user_id=user_id,
                event_type=event_type,
                severity=severity,
                title=title,
                body=body,
                payload=payload,
            )
        )
        log_delivery(
            db,
            channel="system",
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            title=title,
            status="sent",
            payload=payload,
        )
    db.flush()
