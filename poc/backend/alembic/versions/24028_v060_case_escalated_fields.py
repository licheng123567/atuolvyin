"""v0.6.0 — 升级案件介入处理字段:陪同监听 + 结案原因

诱因:督导「介入处理」5 选项中:
  ② 标记陪同监听 — 需 case.shadow_supervisor_id 字段
  ③ 直接结案 / 标坏账 — 需 case.close_reason 字段(并 stage → 'pending_close' 等物业管理员二审)

变更:
1. collection_case.shadow_supervisor_id BIGINT NULL FK → user_account.id
2. collection_case.close_reason TEXT NULL

Revision ID: 24028v060b
Revises: 24027v060a
Create Date: 2026-05-20 22:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24028v060b"
down_revision: str | None = "24027v060a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "collection_case",
        sa.Column(
            "shadow_supervisor_id",
            sa.BigInteger(),
            sa.ForeignKey("user_account.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "collection_case",
        sa.Column("close_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("collection_case", "close_reason")
    op.drop_column("collection_case", "shadow_supervisor_id")
