"""v1.9.7 — 工单跟进记录表

Revision ID: 24013v197
Revises: 24012v191
Create Date: 2026-05-12 03:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24013v197"
down_revision: str | None = "24012v191"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "work_order_follow_up",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.BigInteger,
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "work_order_id",
            sa.BigInteger,
            sa.ForeignKey("work_order.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.BigInteger,
            sa.ForeignKey("collection_case.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "actor_user_id",
            sa.BigInteger,
            sa.ForeignKey("user_account.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="note"),
        sa.Column("note", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "kind IN ('note','resolution_proposed','escalation')",
            name="ck_work_order_followup_kind",
        ),
    )
    op.create_index("ix_work_order_follow_up_tenant_id", "work_order_follow_up", ["tenant_id"])
    op.create_index("ix_work_order_follow_up_work_order_id", "work_order_follow_up", ["work_order_id"])
    op.create_index("ix_work_order_follow_up_case_id", "work_order_follow_up", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_work_order_follow_up_case_id", table_name="work_order_follow_up")
    op.drop_index("ix_work_order_follow_up_work_order_id", table_name="work_order_follow_up")
    op.drop_index("ix_work_order_follow_up_tenant_id", table_name="work_order_follow_up")
    op.drop_table("work_order_follow_up")
