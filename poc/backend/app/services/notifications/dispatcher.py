"""通知分发主入口 (Sprint 15.4 / PRD §L412)。

dispatch(db, *, tenant_id, event_type, title, body, recipient_user_ids, severity, payload)

行为：
  1. 读取 TenantSettings；若该 event_type 对应字段是 False → 整体不发
  2. 否则按 settings.notify_channels 路由到各渠道处理器
  3. 每个渠道独立异常隔离，单个渠道失败不阻塞其他
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.settings import TenantSettings

from .channels import dingtalk as ch_dingtalk
from .channels import sms as ch_sms
from .channels import system as ch_system
from .channels import wechat as ch_wechat

logger = logging.getLogger(__name__)


class EventType(StrEnum):
    """5 个 PRD §L412 事件类型，与 TenantSettings notify_xxx 字段一一对应。"""

    QUOTA_WARNING = "quota_warning"
    SCRIPT_DISABLED = "script_disabled"
    WORK_ORDER_COMPLETED = "work_order_completed"
    CASE_ESCALATED = "case_escalated"
    PROMISE_EXPIRING = "promise_expiring"


# 事件类型 → TenantSettings 列名映射
_EVENT_TO_SETTING_FLAG = {
    EventType.QUOTA_WARNING: "notify_quota_warning",
    EventType.SCRIPT_DISABLED: "notify_script_disabled",
    EventType.WORK_ORDER_COMPLETED: "notify_work_order_completed",
    EventType.CASE_ESCALATED: "notify_case_escalated",
    EventType.PROMISE_EXPIRING: "notify_promise_expiring",
}


_CHANNEL_HANDLERS = {
    "system": ch_system.send,
    "sms": ch_sms.send,
    "wechat": ch_wechat.send,
    "dingtalk": ch_dingtalk.send,
}


def _get_settings(db: Session, tenant_id: int) -> TenantSettings | None:
    return db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    ).scalar_one_or_none()


def dispatch(
    db: Session,
    *,
    tenant_id: int,
    event_type: EventType,
    title: str,
    body: str,
    recipient_user_ids: list[int],
    severity: str = "info",
    payload: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    """同步分发一条通知。返回 {"sent": [channels], "skipped": [...], "failed": [...]}.

    调用方负责 db.commit()（system 渠道写表只 flush，commit 由调用方控制）。
    """
    result = {"sent": [], "skipped": [], "failed": []}
    settings = _get_settings(db, tenant_id)

    # 事件总开关：若 settings 缺失，按 PRD 默认全部开启 → 仍发；否则查字段
    if settings is not None:
        flag_attr = _EVENT_TO_SETTING_FLAG.get(event_type)
        if flag_attr and not getattr(settings, flag_attr, True):
            logger.info(
                "notification skipped (event %s disabled by tenant %s)",
                event_type,
                tenant_id,
            )
            result["skipped"].append("event_disabled")
            return result

    # 渠道选择：settings 缺失时默认 system；否则用 notify_channels
    channels: list[str] = ["system"]
    if settings is not None and settings.notify_channels:
        channels = list(settings.notify_channels)
    if not channels:
        channels = ["system"]

    for ch in channels:
        handler = _CHANNEL_HANDLERS.get(ch)
        if handler is None:
            logger.warning("unknown notification channel %r", ch)
            result["failed"].append(ch)
            continue
        try:
            handler(
                db,
                tenant_id=tenant_id,
                event_type=event_type.value,
                severity=severity,
                title=title,
                body=body,
                recipient_user_ids=recipient_user_ids,
                payload=payload,
            )
            result["sent"].append(ch)
        except Exception as exc:
            logger.exception("notification channel %s failed: %s", ch, exc)
            result["failed"].append(ch)
    return result
