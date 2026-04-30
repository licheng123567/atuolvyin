"""add_device_profile

Revision ID: f398859a9fb3
Revises: 3c2c07e33ffd
Create Date: 2026-04-30 06:23:10.908975

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f398859a9fb3'
down_revision: Union[str, None] = '3c2c07e33ffd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_profile",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("os_version", sa.Text(), nullable=True),
        sa.Column("last_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_healthy",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
    )
    op.create_index(
        "idx_device_profile_tenant_user",
        "device_profile",
        ["tenant_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_device_profile_tenant_user", table_name="device_profile")
    op.drop_table("device_profile")
