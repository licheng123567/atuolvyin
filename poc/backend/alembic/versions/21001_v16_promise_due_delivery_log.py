"""v1.6 — collection_case.promise_due_at + notification_delivery_log

Revision ID: 21001v16
Revises: 20001v16
Create Date: 2026-05-07 00:00:00.000000

承诺还款到期时间字段 + 通知渠道送达流水表，支撑 PRD §L412 通知闭环：
- promise_due_at 让 scan_and_notify_promise_expiring 真扫描（之前 hasattr stub）
- notification_delivery_log 让 SMS/微信/钉钉/系统站内信 4 个渠道发送行为
  落地为可查询审计记录，方便 admin 排查"为什么这条没收到"
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '21001v16'
down_revision: str | None = '20001v16'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "collection_case",
        sa.Column("promise_due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_case_promise_due_at",
        "collection_case",
        ["promise_due_at"],
        postgresql_where=sa.text("promise_due_at IS NOT NULL"),
    )

    op.create_table(
        "notification_delivery_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),  # sent / skipped / failed
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "channel IN ('system','sms','wechat','dingtalk')",
            name="ck_delivery_channel",
        ),
        sa.CheckConstraint(
            "status IN ('sent','skipped','failed')", name="ck_delivery_status"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_delivery_log_tenant_event",
        "notification_delivery_log",
        ["tenant_id", "event_type"],
    )
    op.create_index(
        "ix_delivery_log_created_at",
        "notification_delivery_log",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_delivery_log_created_at", table_name="notification_delivery_log")
    op.drop_index(
        "ix_delivery_log_tenant_event", table_name="notification_delivery_log"
    )
    op.drop_table("notification_delivery_log")
    op.drop_index("ix_case_promise_due_at", table_name="collection_case")
    op.drop_column("collection_case", "promise_due_at")
