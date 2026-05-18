"""Phase 2 — supervisor_shift / swap_request 加 provider_id + 换唯一约束

Revision ID: 24019v220e
Revises: 24018v220d
Create Date: 2026-05-18 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24019v220e"
down_revision: str | None = "24018v220d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 此处 FK ondelete 刻意用 CASCADE 而非 24018 的 SET NULL：
    # provider 删除时其排班/调班行应一并删除，不能掉回 provider_id IS NULL 的物业 scope。
    # 两表加 provider_id（NULL=物业 / 非NULL=服务商）
    op.add_column("supervisor_shift", sa.Column("provider_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_supervisor_shift_provider",
        "supervisor_shift", "service_provider",
        ["provider_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_supervisor_shift_provider_id", "supervisor_shift", ["provider_id"])

    op.add_column(
        "supervisor_shift_swap_request",
        sa.Column("provider_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_supervisor_shift_swap_request_provider",
        "supervisor_shift_swap_request", "service_provider",
        ["provider_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index(
        "ix_supervisor_shift_swap_request_provider_id",
        "supervisor_shift_swap_request", ["provider_id"],
    )

    # SupervisorShift 旧唯一约束 → 两个 partial unique index
    op.drop_constraint("uq_supervisor_shift_tenant_date_slot", "supervisor_shift", type_="unique")
    op.create_index(
        "uq_supervisor_shift_property",
        "supervisor_shift", ["tenant_id", "shift_date", "slot"],
        unique=True, postgresql_where=sa.text("provider_id IS NULL"),
    )
    op.create_index(
        "uq_supervisor_shift_provider",
        "supervisor_shift", ["tenant_id", "provider_id", "shift_date", "slot"],
        unique=True, postgresql_where=sa.text("provider_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_supervisor_shift_provider", table_name="supervisor_shift")
    op.drop_index("uq_supervisor_shift_property", table_name="supervisor_shift")
    op.create_unique_constraint(
        "uq_supervisor_shift_tenant_date_slot",
        "supervisor_shift", ["tenant_id", "shift_date", "slot"],
    )
    op.drop_index(
        "ix_supervisor_shift_swap_request_provider_id",
        table_name="supervisor_shift_swap_request",
    )
    op.drop_constraint(
        "fk_supervisor_shift_swap_request_provider",
        "supervisor_shift_swap_request", type_="foreignkey",
    )
    op.drop_column("supervisor_shift_swap_request", "provider_id")
    op.drop_index("ix_supervisor_shift_provider_id", table_name="supervisor_shift")
    op.drop_constraint("fk_supervisor_shift_provider", "supervisor_shift", type_="foreignkey")
    op.drop_column("supervisor_shift", "provider_id")
