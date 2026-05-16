"""Sprint 15.4 — 通话分钟池化配额预警 (PRD §20.1.1 / §L412).

每次扣分钟后调用 check_and_notify_quota_thresholds，跨阈值时触发通知：
  - 80%   → severity=info
  - 95%   → severity=warn
  - 100%  → severity=critical

接收人：本租户所有 admin + 平台运营员（ops 通过 PlatformOpsAssignment 找到）。

跨阈值判定：previous_used 和 current_used 中只有一方已过阈值时才发；
保证同一阈值不会重复触发。
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant, UserTenantMembership
from app.models.user import PlatformOpsAssignment
from app.services.notifications import EventType, dispatch

logger = logging.getLogger(__name__)

THRESHOLDS = [
    (0.80, "info", "本月通话已用 80%"),
    (0.95, "warn", "本月通话已用 95%"),
    (1.00, "critical", "本月通话配额已用尽"),
]


def _admin_user_ids(db: Session, tenant_id: int) -> list[int]:
    rows = (
        db.execute(
            select(UserTenantMembership.user_id).where(
                UserTenantMembership.tenant_id == tenant_id,
                UserTenantMembership.role == "admin",
                UserTenantMembership.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )
    return [int(r) for r in rows]


def _ops_user_ids_for_tenant(db: Session, tenant_id: int) -> list[int]:
    rows = (
        db.execute(
            select(PlatformOpsAssignment.ops_user_id).where(
                PlatformOpsAssignment.entity_type == "tenant",
                PlatformOpsAssignment.entity_id == tenant_id,
            )
        )
        .scalars()
        .all()
    )
    return [int(r) for r in rows]


def check_and_notify_quota_thresholds(
    db: Session,
    *,
    tenant: Tenant,
    previous_used: int,
    current_used: int,
    quota: int,
) -> list[float]:
    """检查跨过的阈值，触发对应通知。返回触发的阈值列表。"""
    if quota <= 0:
        return []
    fired: list[float] = []
    for ratio, severity, title in THRESHOLDS:
        threshold_minutes = ratio * quota
        if previous_used < threshold_minutes <= current_used:
            recipients = list(
                set(_admin_user_ids(db, tenant.id) + _ops_user_ids_for_tenant(db, tenant.id))
            )
            if not recipients:
                logger.info(
                    "quota threshold %.0f%% reached for tenant=%s but no recipients",
                    ratio * 100,
                    tenant.id,
                )
                continue
            body = (
                f"租户「{tenant.name}」本月通话已用 {current_used} / {quota} 分钟"
                f"（{current_used / quota * 100:.1f}%）。"
            )
            try:
                dispatch(
                    db,
                    tenant_id=tenant.id,
                    event_type=EventType.QUOTA_WARNING,
                    title=title,
                    body=body,
                    recipient_user_ids=recipients,
                    severity=severity,
                    payload={
                        "tenant_id": tenant.id,
                        "tenant_name": tenant.name,
                        "used_minutes": current_used,
                        "quota": quota,
                        "ratio": ratio,
                    },
                )
                fired.append(ratio)
            except Exception as exc:
                logger.exception("quota notify dispatch failed: %s", exc)
    return fired
