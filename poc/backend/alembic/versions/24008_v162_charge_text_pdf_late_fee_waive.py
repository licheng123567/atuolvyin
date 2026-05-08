"""v1.6.2 — 收费标准文本化 + 合同 PDF 文件名 + 滞纳金减免独立策略

Revision ID: 24008v162
Revises: 24007v161
Create Date: 2026-05-08 09:00:00.000000

3 个改动：
1. project.charge_rate_text — 自由文本（替代严格 numeric 的 charge_rate_per_sqm）
2. project.contract_attachment_filename — 上传 PDF 的原始文件名（用于下载展示）
3. project + tenant_settings 加 late_fee_waive_* 三件套（滞纳金减免独立策略）
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24008v162"
down_revision: str | None = "24007v161"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── project: 收费标准文本 + 合同附件文件名 ──
    op.add_column("project", sa.Column("charge_rate_text", sa.Text(), nullable=True))
    op.add_column("project", sa.Column("contract_attachment_filename", sa.Text(), nullable=True))

    # ── project: 滞纳金减免独立策略（项目级覆盖） ──
    op.add_column("project", sa.Column("late_fee_waive_auto_approve_threshold_pct", sa.SmallInteger(), nullable=True))
    op.add_column("project", sa.Column("late_fee_waive_supervisor_max_pct", sa.SmallInteger(), nullable=True))
    op.add_column("project", sa.Column("late_fee_waive_disabled", sa.Boolean(), nullable=True))
    op.create_check_constraint(
        "ck_project_late_fee_waive_auto_threshold",
        "project",
        "late_fee_waive_auto_approve_threshold_pct IS NULL OR late_fee_waive_auto_approve_threshold_pct BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_project_late_fee_waive_supervisor_max",
        "project",
        "late_fee_waive_supervisor_max_pct IS NULL OR late_fee_waive_supervisor_max_pct BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_project_late_fee_waive_thresholds_order",
        "project",
        "late_fee_waive_auto_approve_threshold_pct IS NULL OR late_fee_waive_supervisor_max_pct IS NULL OR late_fee_waive_auto_approve_threshold_pct <= late_fee_waive_supervisor_max_pct",
    )

    # ── tenant_settings: 滞纳金减免（默认更宽松：50% 自动 / 100% 督导可批） ──
    op.add_column(
        "tenant_settings",
        sa.Column(
            "late_fee_waive_auto_approve_threshold_pct",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("50"),
        ),
    )
    op.add_column(
        "tenant_settings",
        sa.Column(
            "late_fee_waive_supervisor_max_pct",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("100"),
        ),
    )
    op.add_column(
        "tenant_settings",
        sa.Column(
            "late_fee_waive_disabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_check_constraint(
        "ck_tenant_settings_late_fee_waive_auto",
        "tenant_settings",
        "late_fee_waive_auto_approve_threshold_pct BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_tenant_settings_late_fee_waive_sup_max",
        "tenant_settings",
        "late_fee_waive_supervisor_max_pct BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_tenant_settings_late_fee_waive_order",
        "tenant_settings",
        "late_fee_waive_auto_approve_threshold_pct <= late_fee_waive_supervisor_max_pct",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tenant_settings_late_fee_waive_order", "tenant_settings", type_="check")
    op.drop_constraint("ck_tenant_settings_late_fee_waive_sup_max", "tenant_settings", type_="check")
    op.drop_constraint("ck_tenant_settings_late_fee_waive_auto", "tenant_settings", type_="check")
    op.drop_column("tenant_settings", "late_fee_waive_disabled")
    op.drop_column("tenant_settings", "late_fee_waive_supervisor_max_pct")
    op.drop_column("tenant_settings", "late_fee_waive_auto_approve_threshold_pct")

    op.drop_constraint("ck_project_late_fee_waive_thresholds_order", "project", type_="check")
    op.drop_constraint("ck_project_late_fee_waive_supervisor_max", "project", type_="check")
    op.drop_constraint("ck_project_late_fee_waive_auto_threshold", "project", type_="check")
    op.drop_column("project", "late_fee_waive_disabled")
    op.drop_column("project", "late_fee_waive_supervisor_max_pct")
    op.drop_column("project", "late_fee_waive_auto_approve_threshold_pct")

    op.drop_column("project", "contract_attachment_filename")
    op.drop_column("project", "charge_rate_text")
