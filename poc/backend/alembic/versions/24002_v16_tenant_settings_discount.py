"""v1.6 — TenantSettings 加 3 个减免审批策略字段

Revision ID: 24002v16
Revises: 24001v157
Create Date: 2026-05-09 09:00:00.000000

物业 admin 可在「系统配置 → 减免审批策略」中调整：
- discount_auto_approve_threshold_pct (默认 10)：折扣 < X% 自动通过
- discount_supervisor_max_pct (默认 30)：折扣 ≤ X% 督导可批；> X% 转 admin
- discount_disabled (默认 false)：true 表示本租户完全禁用减免功能
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '24002v16'
down_revision: str | None = '24001v157'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenant_settings",
        sa.Column(
            "discount_auto_approve_threshold_pct",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("10"),
        ),
    )
    op.add_column(
        "tenant_settings",
        sa.Column(
            "discount_supervisor_max_pct",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("30"),
        ),
    )
    op.add_column(
        "tenant_settings",
        sa.Column(
            "discount_disabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_check_constraint(
        "ck_tenant_settings_discount_auto_threshold",
        "tenant_settings",
        "discount_auto_approve_threshold_pct BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_tenant_settings_discount_supervisor_max",
        "tenant_settings",
        "discount_supervisor_max_pct BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_tenant_settings_discount_thresholds_order",
        "tenant_settings",
        "discount_auto_approve_threshold_pct <= discount_supervisor_max_pct",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_tenant_settings_discount_thresholds_order", "tenant_settings", type_="check"
    )
    op.drop_constraint(
        "ck_tenant_settings_discount_supervisor_max", "tenant_settings", type_="check"
    )
    op.drop_constraint(
        "ck_tenant_settings_discount_auto_threshold", "tenant_settings", type_="check"
    )
    op.drop_column("tenant_settings", "discount_disabled")
    op.drop_column("tenant_settings", "discount_supervisor_max_pct")
    op.drop_column("tenant_settings", "discount_auto_approve_threshold_pct")
