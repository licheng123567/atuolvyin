"""企业微信 Bot Webhook 渠道 (Sprint 15.4)。

环境变量 AUTOLUYIN_WECHAT_BOT_URL 配置租户级 webhook URL；缺失则 log-only。
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
    url = os.getenv("AUTOLUYIN_WECHAT_BOT_URL")
    msg = f"[{severity.upper()}] {title}\n{body}"
    if not url:
        logger.info("[WeChat-stub] tenant=%s event=%s | %s", tenant_id, event_type, msg)
        return
    # 异步调用避免阻塞主请求；FastAPI 同步上下文这里用 requests 简化
    try:
        import requests
        resp = requests.post(
            url,
            json={"msgtype": "text", "text": {"content": msg}},
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning("WeChat webhook returned %s: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.exception("WeChat webhook call failed: %s", exc)
