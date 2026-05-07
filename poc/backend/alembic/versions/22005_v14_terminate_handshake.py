"""v1.4 — provider_tenant_contract 加双向解约握手字段（D2）

Revision ID: 22005v14
Revises: 22004v14
Create Date: 2026-05-07 17:00:00.000000

字段：
- termination_requested_by SMALLINT (1=property/物业, 2=provider/服务商)
- termination_requested_at TIMESTAMPTZ
- termination_reason TEXT
- termination_confirmed_at TIMESTAMPTZ
- terminated_at TIMESTAMPTZ — 实际终止时间（status='terminated' 那一刻），用于
  解约后数据可见性窗口（30 天只读 / 60 天软删）
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '22005v14'
down_revision: str | None = '22004v14'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provider_tenant_contract",
        sa.Column("termination_requested_by", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "provider_tenant_contract",
        sa.Column(
            "termination_requested_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "provider_tenant_contract",
        sa.Column("termination_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "provider_tenant_contract",
        sa.Column(
            "termination_confirmed_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "provider_tenant_contract",
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_provider_tenant_contract_term_by",
        "provider_tenant_contract",
        "termination_requested_by IS NULL OR termination_requested_by IN (1,2)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_provider_tenant_contract_term_by",
        "provider_tenant_contract",
        type_="check",
    )
    op.drop_column("provider_tenant_contract", "terminated_at")
    op.drop_column("provider_tenant_contract", "termination_confirmed_at")
    op.drop_column("provider_tenant_contract", "termination_reason")
    op.drop_column("provider_tenant_contract", "termination_requested_at")
    op.drop_column("provider_tenant_contract", "termination_requested_by")
