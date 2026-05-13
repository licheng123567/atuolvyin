"""v2.1 — 设备录音能力探测留痕表 (PRD § 8.4)

Revision ID: 24014v210
Revises: 24013v197
Create Date: 2026-05-12 09:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24014v210"
down_revision: str | None = "24013v197"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_capability_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.BigInteger,
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("device_id", sa.String(64), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("manufacturer", sa.String(32), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("android_version", sa.String(16), nullable=True),
        sa.Column("rom_label", sa.String(32), nullable=True),
        sa.Column("capability", sa.String(16), nullable=False),
        sa.Column("actual_recording_works", sa.Boolean, nullable=True),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.CheckConstraint(
            "capability IN ('realtime','post_upload','incompatible')",
            name="ck_device_capability_log_capability",
        ),
        sa.CheckConstraint(
            "source IN ('static_matrix','runtime_verified')",
            name="ck_device_capability_log_source",
        ),
    )
    op.create_index(
        "ix_device_capability_log_tenant_user_time",
        "device_capability_log",
        ["tenant_id", "user_id", "detected_at"],
    )
    op.create_index(
        "ix_device_capability_log_device",
        "device_capability_log",
        ["device_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_device_capability_log_device",
        table_name="device_capability_log",
    )
    op.drop_index(
        "ix_device_capability_log_tenant_user_time",
        table_name="device_capability_log",
    )
    op.drop_table("device_capability_log")
