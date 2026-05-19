"""缴费链接 — Project 收款字段 + payment_link 表

Revision ID: 24022v220h
Revises: 24021v220g
Create Date: 2026-05-19 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24022v220h"
down_revision: str | None = "24021v220g"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project",
        sa.Column(
            "payment_mode",
            sa.String(length=16),
            nullable=False,
            server_default="property_self",
        ),
    )
    op.add_column("project", sa.Column("payee_name", sa.Text(), nullable=True))
    op.add_column("project", sa.Column("payee_account", sa.Text(), nullable=True))
    op.add_column("project", sa.Column("payee_qr_object_key", sa.Text(), nullable=True))
    op.add_column("project", sa.Column("payment_instructions", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_project_payment_mode",
        "project",
        "payment_mode IN ('property_self','notary_escrow')",
    )
    op.create_table(
        "payment_link",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("case_id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "payment_mode",
            sa.String(length=16),
            nullable=False,
            server_default="property_self",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["case_id"], ["collection_case.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["user_account.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_payment_link_token"),
        sa.CheckConstraint(
            "payment_mode IN ('property_self','notary_escrow')",
            name="ck_payment_link_payment_mode",
        ),
    )
    op.create_index("ix_payment_link_case", "payment_link", ["case_id"])
    op.create_index("ix_payment_link_tenant", "payment_link", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_link_tenant", table_name="payment_link")
    op.drop_index("ix_payment_link_case", table_name="payment_link")
    op.drop_table("payment_link")
    op.drop_constraint("ck_project_payment_mode", "project", type_="check")
    op.drop_column("project", "payment_instructions")
    op.drop_column("project", "payee_qr_object_key")
    op.drop_column("project", "payee_account")
    op.drop_column("project", "payee_name")
    op.drop_column("project", "payment_mode")
