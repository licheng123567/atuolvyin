"""v1.4 — project.allow_internal_assist（服务商项目下允许物业内勤协助）

Revision ID: 22002v14
Revises: 22001v14
Create Date: 2026-05-07 13:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '22002v14'
down_revision: str | None = '22001v14'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project",
        sa.Column(
            "allow_internal_assist",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("project", "allow_internal_assist")
