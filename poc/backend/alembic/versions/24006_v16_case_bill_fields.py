"""v1.6 — CollectionCase 加 账单透明字段

Revision ID: 24006v16
Revises: 24005v16
Create Date: 2026-05-09 12:00:00.000000

详情页「按月推算」需要原始账单数据，新增：
- bill_period_start / bill_period_end (Date)：账单起止日
- principal_amount (Numeric)：本金合计
- late_fee_amount (Numeric)：滞纳金合计
- arrears_reason (Text)：业主欠费理由（导入时录入）

amount_owed = principal + late_fee（保留作为冗余总额，避免破坏现有读路径）
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '24006v16'
down_revision: str | None = '24005v16'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("collection_case", sa.Column("bill_period_start", sa.Date(), nullable=True))
    op.add_column("collection_case", sa.Column("bill_period_end", sa.Date(), nullable=True))
    op.add_column("collection_case", sa.Column("principal_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("collection_case", sa.Column("late_fee_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("collection_case", sa.Column("arrears_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("collection_case", "arrears_reason")
    op.drop_column("collection_case", "late_fee_amount")
    op.drop_column("collection_case", "principal_amount")
    op.drop_column("collection_case", "bill_period_end")
    op.drop_column("collection_case", "bill_period_start")
