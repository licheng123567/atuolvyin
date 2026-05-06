"""Sprint 15.4 — 站内信表 (PRD §L412 通知规则真触发).

存放系统给特定用户推送的通知。Sprint 12.3 落地了「通知规则配置」，
本 sprint 让规则真正触发并把消息送达；本表是 system 渠道的落点。
SMS / 企微 / 钉钉 渠道在 services/notifications/channels/ 下分别实现。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="info")
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.CheckConstraint(
            "severity IN ('info','warn','critical')",
            name="ck_notification_severity",
        ),
        sa.Index("ix_notification_user_unread", "user_id", "read_at"),
    )
