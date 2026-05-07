"""企业微信 Bot Webhook 渠道 (Sprint 15.4)。

环境变量 AUTOLUYIN_WECHAT_BOT_URL 配置租户级 webhook URL；缺失则 log-only。
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy.orm import Session

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
    url = os.getenv("AUTOLUYIN_WECHAT_BOT_URL")
    msg = f"[{severity.upper()}] {title}\n{body}"
    if not url:
        logger.info("[WeChat-stub] tenant=%s event=%s | %s", tenant_id, event_type, msg)
        log_delivery(
            db,
            channel="wechat",
            tenant_id=tenant_id,
            user_id=None,
            event_type=event_type,
            severity=severity,
            title=title,
            status="skipped",
            error="AUTOLUYIN_WECHAT_BOT_URL not set (dev stub)",
            payload=payload,
        )
        return
    status = "sent"
    error: str | None = None
    try:
        import requests
        resp = requests.post(
            url,
            json={"msgtype": "text", "text": {"content": msg}},
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning("WeChat webhook returned %s: %s", resp.status_code, resp.text[:200])
            status = "failed"
            error = f"HTTP {resp.status_code}"
    except Exception as exc:
        logger.exception("WeChat webhook call failed: %s", exc)
        status = "failed"
        error = str(exc)[:200]
    log_delivery(
        db,
        channel="wechat",
        tenant_id=tenant_id,
        user_id=None,
        event_type=event_type,
        severity=severity,
        title=title,
        status=status,
        error=error,
        payload=payload,
    )
