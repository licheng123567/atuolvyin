"""v2.2 — script_template 补 project_id 列（model 有列但无迁移）

Revision ID: 24016v220b
Revises: 24015v220
Create Date: 2026-05-16 10:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24016v220b"
down_revision: str | None = "24015v220"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "script_template",
        sa.Column(
            "project_id",
            sa.BigInteger,
            sa.ForeignKey("project.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("script_template", "project_id")
