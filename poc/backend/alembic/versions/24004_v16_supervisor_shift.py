"""v1.6 — supervisor_shift + supervisor_shift_swap_request 持久化排班

Revision ID: 24004v16
Revises: 24003v16
Create Date: 2026-05-09 10:00:00.000000

替代 supervisor_shifts.py 中的 in-memory _SHIFT_STORE / _SWAP_REQUESTS。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '24004v16'
down_revision: str | None = '24003v16'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "supervisor_shift",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.BigInteger(),
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("shift_date", sa.Date(), nullable=False),
        sa.Column("slot", sa.String(16), nullable=False),
        sa.Column(
            "supervisor_user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_account.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("supervisor_name", sa.String(120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "slot IN ('morning', 'afternoon', 'evening')",
            name="ck_supervisor_shift_slot",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "shift_date",
            "slot",
            name="uq_supervisor_shift_tenant_date_slot",
        ),
    )
    op.create_index(
        "ix_supervisor_shift_tenant_id", "supervisor_shift", ["tenant_id"]
    )
    op.create_index(
        "ix_supervisor_shift_tenant_date",
        "supervisor_shift",
        ["tenant_id", "shift_date"],
    )

    op.create_table(
        "supervisor_shift_swap_request",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.BigInteger(),
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_user_name", sa.String(120), nullable=False),
        sa.Column("to_user_name", sa.String(120), nullable=False),
        sa.Column("shift_date", sa.Date(), nullable=False),
        sa.Column("slot", sa.String(16), nullable=False),
        sa.Column(
            "status",
            sa.String(24),
            nullable=False,
            server_default="pending_confirm",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "slot IN ('morning', 'afternoon', 'evening')",
            name="ck_swap_request_slot",
        ),
        sa.CheckConstraint(
            "status IN ('pending_confirm', 'accepted', 'rejected', 'cancelled')",
            name="ck_swap_request_status",
        ),
    )
    op.create_index(
        "ix_swap_request_tenant_id",
        "supervisor_shift_swap_request",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_swap_request_tenant_id", table_name="supervisor_shift_swap_request")
    op.drop_table("supervisor_shift_swap_request")
    op.drop_index("ix_supervisor_shift_tenant_date", table_name="supervisor_shift")
    op.drop_index("ix_supervisor_shift_tenant_id", table_name="supervisor_shift")
    op.drop_table("supervisor_shift")
