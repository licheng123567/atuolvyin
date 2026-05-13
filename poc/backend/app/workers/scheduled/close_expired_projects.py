"""v1.5.5 — Daily worker：自动关闭服务期到期项目 + 30 天临期提醒（D3）。

调用方式：
    python -m app.workers.scheduled.close_expired_projects

部署时由 systemd timer / Kubernetes CronJob / n8n 每日触发一次。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select

from app.core.db import SessionLocal
from app.models.case import Project
from app.models.notification import Notification
from app.models.tenant import UserTenantMembership
from app.services.audit import log_audit

logger = logging.getLogger("worker.close_expired_projects")

# D3 决策：到期前 30 天单次提醒
EXPIRING_LEAD_DAYS = 30
# 通知去重窗口（同 user + 同项目 link 7 天内不重发）
DEDUP_DAYS = 7


def _project_link(project_id: int) -> str:
    return f"/admin/projects/{project_id}/edit"


def _notify_users_for_project(db, project: Project, *, title: str, body: str, severity: str) -> int:
    """给该项目相关的物业 admin + 服务商 admin 发通知，去重写入。"""
    # 找物业方接收人：项目所属租户的 admin
    recipients: list[tuple[int, int]] = []  # (user_id, tenant_id)
    property_admin_ids = (
        db.execute(
            select(UserTenantMembership.user_id).where(
                UserTenantMembership.tenant_id == project.tenant_id,
                UserTenantMembership.role == "admin",
                UserTenantMembership.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )
    for uid in property_admin_ids:
        recipients.append((int(uid), int(project.tenant_id)))

    # 找服务商方接收人：项目 provider_id 对应的 provider_admin
    if project.provider_id is not None:
        provider_admin_ids = (
            db.execute(
                select(UserTenantMembership.user_id).where(
                    UserTenantMembership.provider_id == project.provider_id,
                    UserTenantMembership.role == "provider_admin",
                    UserTenantMembership.is_active.is_(True),
                )
            )
            .scalars()
            .all()
        )
        for uid in provider_admin_ids:
            recipients.append((int(uid), int(project.tenant_id)))

    sent = 0
    cutoff = datetime.now(UTC) - timedelta(days=DEDUP_DAYS)
    link = _project_link(project.id)
    for user_id, tenant_id in recipients:
        # 去重：7 天内同 user + 同 project 的同 event_type 通知不重发
        existing = db.execute(
            select(Notification.id)
            .where(
                Notification.user_id == user_id,
                Notification.event_type == "project.expiring",
                Notification.created_at >= cutoff,
                # payload 含 project_id（直接用 SQL JSONB）
                Notification.payload["project_id"].astext == str(project.id),
            )
            .limit(1)
        ).scalar_one_or_none()
        if existing is not None:
            continue
        db.add(
            Notification(
                tenant_id=tenant_id,
                user_id=user_id,
                event_type="project.expiring",
                severity=severity,
                title=title,
                body=body,
                payload={"project_id": project.id, "link": link},
            )
        )
        sent += 1
    return sent


def run() -> dict[str, int]:
    """两步：
    1) 关闭所有 active + plan_end < now 的项目 → status='closed' + 写 audit
    2) 扫描 plan_end 在 [now, now+30d] 的 active 项目 → 双向发提醒（去重 7 天）
    """
    closed_count = 0
    notif_count = 0
    now = datetime.now(UTC)
    horizon = now + timedelta(days=EXPIRING_LEAD_DAYS)
    with SessionLocal() as db:
        # Step 1: auto-close
        expired = (
            db.execute(
                select(Project).where(
                    Project.status == "active",
                    Project.plan_end.is_not(None),
                    Project.plan_end < now,
                )
            )
            .scalars()
            .all()
        )
        for p in expired:
            p.status = "closed"
            log_audit(
                db,
                actor_user_id=None,
                actor_role="system",
                tenant_id=p.tenant_id,
                action="project.auto_closed",
                target_type="project",
                target_id=p.id,
                payload={
                    "project_name": p.name,
                    "plan_end": p.plan_end.isoformat() if p.plan_end else None,
                    "provider_id": p.provider_id,
                },
            )
            # 关闭时通知
            notif_count += _notify_users_for_project(
                db,
                p,
                title=f"项目「{p.name}」服务期已到期，已自动关闭",
                body=(
                    f"该项目已于 {now.strftime('%Y-%m-%d')} 到期。如需续约请编辑项目并延长服务期。"
                ),
                severity="warn",
            )
            closed_count += 1

        # Step 2: 临期提醒（30 天内）
        expiring = (
            db.execute(
                select(Project).where(
                    Project.status == "active",
                    Project.plan_end.is_not(None),
                    and_(Project.plan_end >= now, Project.plan_end <= horizon),
                )
            )
            .scalars()
            .all()
        )
        for p in expiring:
            days_left = max(0, (p.plan_end - now).days)
            notif_count += _notify_users_for_project(
                db,
                p,
                title=f"项目「{p.name}」即将到期",
                body=(
                    f"距离服务期到期还有 {days_left} 天（{p.plan_end.strftime('%Y-%m-%d')}）。"
                    f"请提前与对方沟通是否续约。"
                ),
                severity="info",
            )

        db.commit()
    logger.info(
        "auto-closed %d expired project(s); sent %d expiring/closed notification(s)",
        closed_count,
        notif_count,
    )
    return {"closed": closed_count, "notifications": notif_count}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(
        f"auto-closed {result['closed']} project(s); sent {result['notifications']} notification(s)"
    )
