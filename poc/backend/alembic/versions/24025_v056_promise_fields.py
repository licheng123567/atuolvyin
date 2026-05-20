"""v0.5.6 — 承诺缴费结构化字段:collection_case 加 promise_content + promise_amount

诱因:之前「标记承诺缴费」只把 stage 改成 'promised' + 写一条自由文本备注,业主到底
承诺什么、承诺多少、什么时候缴全部丢在 note 里。报表/提醒/兑现追踪都拿不到结构化数据。

本迁移:
- 加 promise_content VARCHAR(500) — 承诺什么(预设清单 + 可选自由文本)
- 加 promise_amount NUMERIC(12,2) — 承诺缴费金额(可空,业主只口头不报金额时允许)
- promise_due_at(承诺缴费日期)已存在(v1.6 加的),复用,本迁移不动

Revision ID: 24025v056a
Revises: 24024v054b
Create Date: 2026-05-20 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24025v056a"
down_revision: str | None = "24024v054b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "collection_case",
        sa.Column("promise_content", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "collection_case",
        sa.Column("promise_amount", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("collection_case", "promise_amount")
    op.drop_column("collection_case", "promise_content")
