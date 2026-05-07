"""阿里云 SMS 渠道 (Sprint 15.4 stub).

Dev 模式仅打 log；生产环境需配置 ALIYUN_ACCESS_KEY_ID / SECRET +
模板 ID 后实现真 HTTP 调用 (alibabacloud-sms20170525 SDK 或 raw HTTP)。
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_phone
from app.models.user import UserAccount

from . import log_delivery

logger = logging.getLogger(__name__)


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
    enabled = os.getenv("AUTOLUYIN_SMS_ENABLED", "false").lower() == "true"
    users = db.execute(
        select(UserAccount).where(UserAccount.id.in_(recipient_user_ids))
    ).scalars().all()
    for u in users:
        try:
            phone = decrypt_phone(u.phone_enc)
        except Exception:
            phone = "(decrypt-failed)"
        if not enabled:
            logger.info(
                "[SMS-stub] tenant=%s event=%s → %s : %s | %s",
                tenant_id, event_type, phone, title, body,
            )
            log_delivery(
                db,
                channel="sms",
                tenant_id=tenant_id,
                user_id=int(u.id),
                event_type=event_type,
                severity=severity,
                title=title,
                status="skipped",
                error="AUTOLUYIN_SMS_ENABLED=false (dev stub)",
                payload=payload,
            )
            continue
        # TODO: 接入阿里云 SMS SDK
        logger.warning("AUTOLUYIN_SMS_ENABLED=true but SDK not yet wired (event=%s)", event_type)
        log_delivery(
            db,
            channel="sms",
            tenant_id=tenant_id,
            user_id=int(u.id),
            event_type=event_type,
            severity=severity,
            title=title,
            status="failed",
            error="SDK not wired",
            payload=payload,
        )
