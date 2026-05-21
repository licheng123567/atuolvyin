"""v0.5.9 — 通话分钟数计费 + 存证消费:加 BillingPricing 表 + Attestation.cost_amount

诱因:用户反馈「物业管理员和服务商管理员就打电话的分钟数消费金额服务,还有物业公司
第三方存证的消费,前端没展示」。Phase 1 调研发现后端也只有数据没有计费 — 没有单价
配置表 / 没有 cost_amount 字段。本迁移补齐数据层。

变更:
1. 新建 billing_pricing 表(单例,平台级单价配置)
2. blockchain_attestation 加 cost_amount Numeric(10,2) NULL(兼容老数据)
3. 默认插入一行 active=True 单价记录(初始价格来自 PRD §20.1.1 + §20.3)

Revision ID: 24026v059a
Revises: 24025v056a
Create Date: 2026-05-20 17:00:00.000000
"""

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa

from alembic import op

revision: str = "24026v059a"
down_revision: str | None = "24025v056a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. billing_pricing 表
    op.create_table(
        "billing_pricing",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("minute_price_live", sa.Numeric(6, 4), nullable=False, server_default="0.5"),
        sa.Column("minute_price_post", sa.Numeric(6, 4), nullable=False, server_default="0.3"),
        sa.Column(
            "blockchain_price_per_attestation",
            sa.Numeric(10, 2), nullable=False, server_default="5",
        ),
        sa.Column(
            "blockchain_price_per_case_bundle",
            sa.Numeric(10, 2), nullable=False, server_default="99",
        ),
        sa.Column(
            "effective_from", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "uq_billing_pricing_active", "billing_pricing", ["is_active"],
        unique=True, postgresql_where=sa.text("is_active = true"),
    )

    # 2. 默认插入一行 active(PRD §20.1.1 / §20.3 价格)
    op.execute(
        "INSERT INTO billing_pricing "
        "(minute_price_live, minute_price_post, "
        " blockchain_price_per_attestation, blockchain_price_per_case_bundle, "
        " is_active) "
        "VALUES (0.5, 0.3, 5, 99, true)"
    )

    # 3. blockchain_attestation 加 cost_amount(NULL = 老数据 / mock 未计费)
    op.add_column(
        "blockchain_attestation",
        sa.Column("cost_amount", sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("blockchain_attestation", "cost_amount")
    op.drop_index("uq_billing_pricing_active", table_name="billing_pricing")
    op.drop_table("billing_pricing")
