"""v0.6.0 — 结算「计费方式」字段补齐

诱因:前端 SettlementItem.billing_method 已展示并出现在导出 CSV,但后端
SettlementStatement 模型缺该字段,导致看板显示「—」。

变更:
1. settlement_statement 加 billing_method VARCHAR(32) NULL
2. CHECK 约束 billing_method IN ('monthly_fee','per_case','percent_of_recovered') OR NULL
3. 历史数据不回填(NULL),由后续生成新结算时按对应 ProviderTenantContract.contract_type
   写入(monthly_fee / per_case / percent_of_recovered 三选一)

Revision ID: 24027v060a
Revises: 24026v059a
Create Date: 2026-05-20 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24027v060a"
down_revision: str | None = "24026v059a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "settlement_statement",
        sa.Column("billing_method", sa.String(length=32), nullable=True),
    )
    op.create_check_constraint(
        "ck_settlement_billing_method",
        "settlement_statement",
        "billing_method IS NULL OR billing_method IN "
        "('monthly_fee','per_case','percent_of_recovered')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_settlement_billing_method", "settlement_statement", type_="check"
    )
    op.drop_column("settlement_statement", "billing_method")
