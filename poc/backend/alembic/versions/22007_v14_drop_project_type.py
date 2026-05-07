"""v1.4 — 移除 project.project_type（系统纯催收，类型字段冗余）

Revision ID: 22007v14
Revises: 22006v14
Create Date: 2026-05-07 19:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '22007v14'
down_revision: str | None = '22006v14'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("project", "project_type")


def downgrade() -> None:
    op.add_column(
        "project",
        sa.Column(
            "project_type",
            sa.Text(),
            nullable=False,
            server_default="collection",
        ),
    )
