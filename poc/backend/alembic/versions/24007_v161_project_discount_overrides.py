"""v1.6.1 — Project 加 项目级减免阈值（覆盖租户级）

Revision ID: 24007v161
Revises: 24006v16
Create Date: 2026-05-09 14:00:00.000000

不同项目（小区 / 商业体 / 写字楼）减免政策可能不同；项目级字段为 NULL 时继承 TenantSettings。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '24007v161'
down_revision: str | None = '24006v16'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project", sa.Column("discount_auto_approve_threshold_pct", sa.SmallInteger(), nullable=True))
    op.add_column("project", sa.Column("discount_supervisor_max_pct", sa.SmallInteger(), nullable=True))
    op.add_column("project", sa.Column("discount_disabled", sa.Boolean(), nullable=True))
    op.create_check_constraint(
        "ck_project_discount_auto_threshold",
        "project",
        "discount_auto_approve_threshold_pct IS NULL OR discount_auto_approve_threshold_pct BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_project_discount_supervisor_max",
        "project",
        "discount_supervisor_max_pct IS NULL OR discount_supervisor_max_pct BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_project_discount_thresholds_order",
        "project",
        "discount_auto_approve_threshold_pct IS NULL OR discount_supervisor_max_pct IS NULL OR discount_auto_approve_threshold_pct <= discount_supervisor_max_pct",
    )


def downgrade() -> None:
    op.drop_constraint("ck_project_discount_thresholds_order", "project", type_="check")
    op.drop_constraint("ck_project_discount_supervisor_max", "project", type_="check")
    op.drop_constraint("ck_project_discount_auto_threshold", "project", type_="check")
    op.drop_column("project", "discount_disabled")
    op.drop_column("project", "discount_supervisor_max_pct")
    op.drop_column("project", "discount_auto_approve_threshold_pct")
