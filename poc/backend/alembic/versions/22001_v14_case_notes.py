"""v1.4 — collection_case.notes（欠费情况说明，导入时录入，催收员一眼看到原因）

Revision ID: 22001v14
Revises: 21001v16
Create Date: 2026-05-07 12:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '22001v14'
down_revision: str | None = '21001v16'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "collection_case",
        sa.Column("notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("collection_case", "notes")
