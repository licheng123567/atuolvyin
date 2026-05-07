"""Sprint 15.4b — 5 事件订阅入口 (PRD §L412)。

每个 notify_xxx 单独函数，签名贴业务上下文。失败做 log，不抛回业务，
保证业务事务不被通知失败回滚。
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import UserTenantMembership
from app.models.user import PlatformOpsAssignment

from .dispatcher import EventType, dispatch

logger = logging.getLogger(__name__)


def _users_with_role(db: Session, tenant_id: int, *roles: str) -> list[int]:
    rows = db.execute(
        select(UserTenantMembership.user_id).where(
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.role.in_(roles),
            UserTenantMembership.is_active.is_(True),
        )
    ).scalars().all()
    return [int(r) for r in rows]


def _ops_users(db: Session, tenant_id: int) -> list[int]:
    rows = db.execute(
        select(PlatformOpsAssignment.ops_user_id).where(
            PlatformOpsAssignment.entity_type == "tenant",
            PlatformOpsAssignment.entity_id == tenant_id,
        )
    ).scalars().all()
    return [int(r) for r in rows]


def _safe_dispatch(db: Session, **kwargs) -> None:
    try:
        dispatch(db, **kwargs)
    except Exception as exc:
        logger.exception("notification dispatch failed: %s", exc)


# ── script_disabled ──────────────────────────────────────────────


def notify_script_disabled(
    db: Session,
    *,
    tenant_id: int,
    script_id: int,
    script_name: str,
    operator_user_id: int | None = None,
) -> None:
    """话术被禁用时通知本租户 admin + supervisor。"""
    recipients = list(set(_users_with_role(db, tenant_id, "admin", "supervisor")))
    if operator_user_id is not None:
        recipients = [u for u in recipients if u != operator_user_id]
    if not recipients:
        return
    _safe_dispatch(
        db,
        tenant_id=tenant_id,
        event_type=EventType.SCRIPT_DISABLED,
        title="话术已停用",
        body=f"话术「{script_name}」已被禁用，相关坐席不再使用该话术。",
        recipient_user_ids=recipients,
        severity="info",
        payload={"script_id": script_id, "script_name": script_name},
    )


# ── work_order_completed ─────────────────────────────────────────


def notify_work_order_completed(
    db: Session,
    *,
    tenant_id: int,
    work_order_id: int,
    title: str,
    creator_user_id: int | None,
    completer_user_id: int | None = None,
) -> None:
    """工单标记完成时通知创建人 + admin。"""
    recipients: list[int] = []
    if creator_user_id is not None:
        recipients.append(int(creator_user_id))
    recipients.extend(_users_with_role(db, tenant_id, "admin"))
    recipients = list({u for u in recipients if u != completer_user_id})
    if not recipients:
        return
    _safe_dispatch(
        db,
        tenant_id=tenant_id,
        event_type=EventType.WORK_ORDER_COMPLETED,
        title="工单已完成",
        body=f"工单 #{work_order_id}「{title}」已被处理完成。",
        recipient_user_ids=recipients,
        severity="info",
        payload={"work_order_id": work_order_id, "title": title},
    )


# ── case_escalated ───────────────────────────────────────────────


def notify_case_escalated(
    db: Session,
    *,
    tenant_id: int,
    case_id: int,
    owner_name: str | None,
    new_stage: str,
    operator_user_id: int | None = None,
) -> None:
    """案件升级到 escalated/legal 等阶段时通知 admin + supervisor + 平台 ops。"""
    recipients = list(set(
        _users_with_role(db, tenant_id, "admin", "supervisor")
        + _ops_users(db, tenant_id)
    ))
    if operator_user_id is not None:
        recipients = [u for u in recipients if u != operator_user_id]
    if not recipients:
        return
    _safe_dispatch(
        db,
        tenant_id=tenant_id,
        event_type=EventType.CASE_ESCALATED,
        title="案件已升级",
        body=(
            f"案件 #{case_id}（业主：{owner_name or '未命名'}）"
            f"已升级到 {new_stage} 阶段。"
        ),
        recipient_user_ids=recipients,
        severity="warn",
        payload={"case_id": case_id, "new_stage": new_stage},
    )


# ── promise_expiring (Celery beat 调度) ──────────────────────────


def scan_and_notify_promise_expiring(
    db: Session,
    *,
    look_ahead_hours: int = 24,
) -> int:
    """扫描即将到期的承诺还款，给案件 assigned_to 发提醒。

    Celery beat 调度：每小时跑一次（或 dev 环境用 mgmt 命令手动跑）。
    依赖 v1.6 alembic 21001v16 添加的 collection_case.promise_due_at 字段。
    """
    from app.models.case import CollectionCase
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    deadline = now + timedelta(hours=look_ahead_hours)
    rows = db.execute(
        select(CollectionCase).where(
            CollectionCase.promise_due_at.isnot(None),
            CollectionCase.promise_due_at <= deadline,
            CollectionCase.promise_due_at > now,
        )
    ).scalars().all()

    fired = 0
    for case in rows:
        if not case.assigned_to:
            continue
        _safe_dispatch(
            db,
            tenant_id=case.tenant_id,
            event_type=EventType.PROMISE_EXPIRING,
            title="承诺还款即将到期",
            body=(
                f"案件 #{case.id} 的承诺还款将于"
                f" {case.promise_due_at:%Y-%m-%d %H:%M} 到期，请及时跟进。"
            ),
            recipient_user_ids=[int(case.assigned_to)],
            severity="warn",
            payload={
                "case_id": case.id,
                "promise_due_at": case.promise_due_at.isoformat(),
            },
        )
        fired += 1
    return fired
