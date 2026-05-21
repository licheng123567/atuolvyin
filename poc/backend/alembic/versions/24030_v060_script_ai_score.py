"""v0.6.0 — 话术 AI 评分字段

诱因:用户反馈「话术好坏督导手工标 / 综合评分公式不透明」,需 AI 基于
案件回款率自动评分。算法:近 30 天 SuggestionFeedback adopted →
CallRecord → CollectionCase.stage='paid' 算回款率;加权 70% 回款 + 30%
采用率,归一化到 0-100。

变更:
1. script_template.ai_score NUMERIC(5,2) NULL — 0-100
2. script_template.ai_score_updated_at TIMESTAMPTZ NULL — 最近重算时间
3. script_template.ai_score_sample_count INTEGER NULL — 样本数(<10 显示「样本不足」)

Revision ID: 24030v060d
Revises: 24029v060c
Create Date: 2026-05-20 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24030v060d"
down_revision: str | None = "24029v060c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "script_template",
        sa.Column("ai_score", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "script_template",
        sa.Column("ai_score_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "script_template",
        sa.Column("ai_score_sample_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("script_template", "ai_score_sample_count")
    op.drop_column("script_template", "ai_score_updated_at")
    op.drop_column("script_template", "ai_score")
