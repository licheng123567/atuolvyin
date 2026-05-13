"""v1.9.1 — closed_promised 加 promise_due_date 列（业主承诺缴清日）

Revision ID: 24012v191
Revises: 24011v190
Create Date: 2026-05-11 18:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24012v191"
down_revision: str | None = "24011v190"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "legal_conversion_order",
        sa.Column("promise_due_date", sa.Date(), nullable=True),
    )
    # 用于「过期未付」列表查询：where status=closed_promised AND promise_due_date < today
    op.create_index(
        "ix_legal_conv_promise_due",
        "legal_conversion_order",
        ["status", "promise_due_date"],
        postgresql_where=sa.text("status = 'closed_promised'"),
    )


def downgrade() -> None:
    op.drop_index("ix_legal_conv_promise_due", table_name="legal_conversion_order")
    op.drop_column("legal_conversion_order", "promise_due_date")
