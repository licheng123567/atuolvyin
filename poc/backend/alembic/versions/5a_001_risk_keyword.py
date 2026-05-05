"""Sprint 5a-001 — risk_keyword table with platform seed data.

Revision ID: 5a001riskword
Revises: 4001a1b2c3d4
Create Date: 2026-05-01 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "5a001riskword"
down_revision = "4001a1b2c3d4"
branch_labels = None
depends_on = None

_SEED = [
    # (category, speaker, level, keyword)
    ("owner_abuse",           "customer", "L1", "你妈"),
    ("owner_abuse",           "customer", "L1", "滚"),
    ("owner_abuse",           "customer", "L1", "傻逼"),
    ("owner_abuse",           "customer", "L1", "神经病"),
    ("owner_abuse",           "customer", "L1", "脑残"),
    ("owner_threat",          "customer", "L2", "投诉"),
    ("owner_threat",          "customer", "L2", "12345"),
    ("owner_threat",          "customer", "L2", "上法院"),
    ("owner_threat",          "customer", "L2", "媒体"),
    ("owner_threat",          "customer", "L2", "律师"),
    ("owner_threat",          "customer", "L2", "曝光"),
    ("agent_violation",       "agent",    "L2", "再不还"),
    ("agent_violation",       "agent",    "L2", "黑名单"),
    ("agent_violation",       "agent",    "L2", "找你单位"),
    ("agent_violation",       "agent",    "L2", "找你家人"),
    ("agent_minor_misconduct","agent",    "L1", "随便你"),
    ("agent_minor_misconduct","agent",    "L1", "爱交不交"),
    ("agent_minor_misconduct","agent",    "L1", "给你减免"),
    ("agent_minor_misconduct","agent",    "L1", "打折"),
]


def upgrade() -> None:
    op.create_table(
        "risk_keyword",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("speaker", sa.String(16), nullable=False),
        sa.Column("level", sa.String(8), nullable=False),
        sa.Column("keyword", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "category", "keyword", name="uq_risk_keyword_tenant_cat_kw"),
    )
    op.create_index(
        "idx_risk_keyword_tenant_speaker",
        "risk_keyword",
        ["tenant_id", "speaker", "is_active"],
    )

    # Seed platform-wide keywords (tenant_id = NULL)
    bulk = op.get_bind()
    bulk.execute(
        sa.text(
            "INSERT INTO risk_keyword (tenant_id, category, speaker, level, keyword) "
            "VALUES (:tenant_id, :category, :speaker, :level, :keyword)"
        ),
        [
            {"tenant_id": None, "category": c, "speaker": s, "level": lv, "keyword": kw}
            for c, s, lv, kw in _SEED
        ],
    )


def downgrade() -> None:
    op.drop_index("idx_risk_keyword_tenant_speaker", table_name="risk_keyword")
    op.drop_table("risk_keyword")
