"""v1.4 — service_provider.recommended_by_tenant_id（物业推荐入驻溯源）

Revision ID: 22003v14
Revises: 22002v14
Create Date: 2026-05-07 14:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '22003v14'
down_revision: str | None = '22002v14'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "service_provider",
        sa.Column(
            "recommended_by_tenant_id",
            sa.BigInteger(),
            sa.ForeignKey("tenant.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("service_provider", "recommended_by_tenant_id")
