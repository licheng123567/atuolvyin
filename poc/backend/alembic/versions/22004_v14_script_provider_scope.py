"""v1.4 — script_template.provider_id（话术三层归属：平台/物业/服务商）

Revision ID: 22004v14
Revises: 22003v14
Create Date: 2026-05-07 16:00:00.000000

三层语义：
  tenant_id NULL & provider_id NULL → 平台预置
  tenant_id NOT NULL & provider_id NULL → 物业私有
  provider_id NOT NULL → 服务商私有
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '22004v14'
down_revision: str | None = '22003v14'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "script_template",
        sa.Column(
            "provider_id",
            sa.BigInteger(),
            sa.ForeignKey("service_provider.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_script_template_provider", "script_template", ["provider_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_script_template_provider", table_name="script_template")
    op.drop_column("script_template", "provider_id")
