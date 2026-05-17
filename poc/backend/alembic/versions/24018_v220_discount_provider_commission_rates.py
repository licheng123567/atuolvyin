"""§9.2 — discount_offer.provider_id + project 佣金率两列

Revision ID: 24018v220d
Revises: 24017v220c
Create Date: 2026-05-17 09:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24018v220d"
down_revision: str | None = "24017v220c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "discount_offer",
        sa.Column("provider_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_discount_offer_provider",
        "discount_offer",
        "service_provider",
        ["provider_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "project",
        sa.Column("internal_agent_commission_rate", sa.Numeric(6, 4), nullable=True),
    )
    op.add_column(
        "project",
        sa.Column("provider_agent_commission_rate", sa.Numeric(6, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project", "provider_agent_commission_rate")
    op.drop_column("project", "internal_agent_commission_rate")
    op.drop_constraint("fk_discount_offer_provider", "discount_offer", type_="foreignkey")
    op.drop_column("discount_offer", "provider_id")
