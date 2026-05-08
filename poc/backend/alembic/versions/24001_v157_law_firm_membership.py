"""v1.5.7 S2 — law_firm_membership 关联表（PRD §20.4）

Revision ID: 24001v157
Revises: 23002v15
Create Date: 2026-05-08 12:00:00.000000

把外部律所代表 / 律师纳入系统账号体系，使其能登录系统访问律所工作台 / 律师工作台。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '24001v157'
down_revision: str | None = '23002v15'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "law_firm_membership",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "law_firm_id",
            sa.BigInteger(),
            sa.ForeignKey("law_firm.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lawyer_id",
            sa.BigInteger(),
            sa.ForeignKey("law_firm_lawyer.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("role_in_firm", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
            "role_in_firm IN ('admin', 'lawyer')",
            name="ck_law_firm_membership_role",
        ),
        sa.UniqueConstraint(
            "user_id", "law_firm_id", name="uq_law_firm_membership_user_firm"
        ),
    )
    op.create_index(
        "ix_law_firm_membership_user_id", "law_firm_membership", ["user_id"]
    )
    op.create_index(
        "ix_law_firm_membership_law_firm_id", "law_firm_membership", ["law_firm_id"]
    )
    op.create_index(
        "ix_law_firm_membership_firm_role",
        "law_firm_membership",
        ["law_firm_id", "role_in_firm"],
    )


def downgrade() -> None:
    op.drop_index("ix_law_firm_membership_firm_role", table_name="law_firm_membership")
    op.drop_index("ix_law_firm_membership_law_firm_id", table_name="law_firm_membership")
    op.drop_index("ix_law_firm_membership_user_id", table_name="law_firm_membership")
    op.drop_table("law_firm_membership")
