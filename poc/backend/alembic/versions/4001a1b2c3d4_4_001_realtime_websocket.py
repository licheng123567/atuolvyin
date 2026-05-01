"""Sprint 4-001 — realtime WebSocket fields + suggestion_feedback table.

Revision ID: 4001a1b2c3d4
Revises: b7e2f19a8c30
Create Date: 2026-04-30 12:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4001a1b2c3d4"
down_revision = "b7e2f19a8c30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "device_profile",
        sa.Column("push_reg_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "device_profile",
        sa.Column("push_provider", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "call_record",
        sa.Column("user_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "suggestion_feedback",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("call_id", sa.BigInteger(), sa.ForeignKey("call_record.id"), nullable=False),
        sa.Column("suggestion_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("suggestion_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("call_id", "suggestion_id", name="uq_suggestion_feedback_call_sid"),
    )
    op.create_index(
        "ix_suggestion_feedback_call_id", "suggestion_feedback", ["call_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_suggestion_feedback_call_id", table_name="suggestion_feedback")
    op.drop_table("suggestion_feedback")
    op.drop_column("call_record", "user_confirmed_at")
    op.drop_column("device_profile", "push_provider")
    op.drop_column("device_profile", "push_reg_id")
