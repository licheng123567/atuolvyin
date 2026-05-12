"""v1.9.7 — 工单跟进记录（协调员/admin 处理工单时的过程笔记）。

每条 follow-up 写入后：
- 在工单详情页中栏「跟进记录」card 显示
- 通过 case_timeline.py 聚合，作为 workorder.followup 事件
  广播到 admin/agent/supervisor/legal 看的「案件活动时间线」
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class WorkOrderFollowUp(Base, TimestampMixin):
    __tablename__ = "work_order_follow_up"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    work_order_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("work_order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # case_id 冗余字段（便于 case_timeline.py 直接按 case 聚合，不必 JOIN work_order）
    case_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("collection_case.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    actor_user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("user_account.id", ondelete="RESTRICT"),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    # kind: note (普通跟进) / resolution_proposed (提建议) / escalation (升级)
    kind: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, default="note"
    )
    note: Mapped[str] = mapped_column(sa.Text, nullable=False)

    __table_args__ = (
        sa.CheckConstraint(
            "kind IN ('note','resolution_proposed','escalation')",
            name="ck_work_order_followup_kind",
        ),
    )
