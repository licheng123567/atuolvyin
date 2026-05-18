"""短信通道 — sms_config 平台级配置表

Revision ID: 24020v220f
Revises: 24019v220e
Create Date: 2026-05-18 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24020v220f"
down_revision: str | None = "24019v220e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sms_config",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("secret_name", sa.String(length=128), nullable=False),
        sa.Column("secret_key_enc", sa.Text(), nullable=True),
        sa.Column("sign_name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("otp_template_id", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("singleton", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("singleton", name="uq_sms_config_singleton"),
    )


def downgrade() -> None:
    op.drop_table("sms_config")
