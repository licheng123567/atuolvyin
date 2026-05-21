"""v1.0.0 — RiskKeyword 加 provider_id(服务商私有风控关键词)

诱因:用户反馈服务商需要自己的风控关键词(1:1 还原物业 admin 的风控关键词管理)。

变更:
1. risk_keyword 表加 provider_id 列(nullable)
2. 删原 uq_risk_keyword_tenant_cat_kw,改 uq_risk_keyword_scope_cat_kw
   (含 provider_id,允许相同 keyword 在物业 vs 服务商各存一份)
3. 加 idx_riskkw_provider_cat_speaker_active 索引
4. CHECK ck_risk_keyword_scope_xor:tenant_id 与 provider_id 不能同时非 NULL
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "24101v100b"
down_revision: str | None = "24100v100a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "risk_keyword",
        sa.Column(
            "provider_id",
            sa.BigInteger(),
            sa.ForeignKey("service_provider.id"),
            nullable=True,
        ),
    )

    # 原 unique 约束改为含 provider_id
    op.drop_constraint(
        "uq_risk_keyword_tenant_cat_kw", "risk_keyword", type_="unique"
    )
    # PG 16 nulls_not_distinct=True — 让 NULL 参与去重(对齐原 (tenant_id, cat, keyword) 行为)
    op.create_unique_constraint(
        "uq_risk_keyword_scope_cat_kw",
        "risk_keyword",
        ["tenant_id", "provider_id", "category", "keyword"],
        postgresql_nulls_not_distinct=True,
    )

    # provider 维度索引
    op.create_index(
        "idx_riskkw_provider_cat_speaker_active",
        "risk_keyword",
        ["provider_id", "category", "speaker", "is_active"],
    )

    # XOR CHECK
    op.create_check_constraint(
        "ck_risk_keyword_scope_xor",
        "risk_keyword",
        "NOT (tenant_id IS NOT NULL AND provider_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_risk_keyword_scope_xor", "risk_keyword", type_="check")
    op.drop_index("idx_riskkw_provider_cat_speaker_active", "risk_keyword")
    op.drop_constraint("uq_risk_keyword_scope_cat_kw", "risk_keyword", type_="unique")
    op.create_unique_constraint(
        "uq_risk_keyword_tenant_cat_kw",
        "risk_keyword",
        ["tenant_id", "category", "keyword"],
    )
    op.drop_column("risk_keyword", "provider_id")
