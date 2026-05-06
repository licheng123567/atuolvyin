"""钉钉 Bot Webhook 渠道 (Sprint 15.4)。

环境变量 AUTOLUYIN_DINGTALK_BOT_URL 配置 webhook URL；缺失则 log-only。
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy.orm import Session

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
    url = os.getenv("AUTOLUYIN_DINGTALK_BOT_URL")
    msg = f"[{severity.upper()}] {title}\n{body}"
    if not url:
        logger.info("[DingTalk-stub] tenant=%s event=%s | %s", tenant_id, event_type, msg)
        return
    try:
        import requests
        resp = requests.post(
            url,
            json={"msgtype": "text", "text": {"content": msg}},
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning("DingTalk webhook returned %s: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.exception("DingTalk webhook call failed: %s", exc)
