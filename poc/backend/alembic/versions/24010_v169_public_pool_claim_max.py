"""v1.6.9 — 公海池抢单上限：每个催收员同时持有未结案案件不超过此数

Revision ID: 24010v169
Revises: 24009v168
Create Date: 2026-05-09 14:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24010v169"
down_revision: str | None = "24009v168"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenant_settings",
        sa.Column(
            "public_pool_claim_max",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("50"),
        ),
    )
    op.create_check_constraint(
        "ck_tenant_settings_pool_claim_max",
        "tenant_settings",
        "public_pool_claim_max BETWEEN 1 AND 1000",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_tenant_settings_pool_claim_max", "tenant_settings", type_="check"
    )
    op.drop_column("tenant_settings", "public_pool_claim_max")
