"""v1.6 — work_order.priority 字段（4 档：很紧急/紧急/一般/低）

Revision ID: 20001v16
Revises: 19004v15
Create Date: 2026-05-06 22:30:00.000000

PRD §10.4 工单原型（ui/workorder.html）展示了 priority 4 档 badge。
之前 React 端无该字段是建模缺口；本次补齐。

新增：work_order.priority VARCHAR(16) NOT NULL DEFAULT 'normal'
约束：CHECK priority IN ('urgent_critical','urgent','normal','low')
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '20001v16'
down_revision: str | None = '19004v15'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "work_order",
        sa.Column(
            "priority",
            sa.String(16),
            nullable=False,
            server_default="normal",
        ),
    )
    op.create_check_constraint(
        "ck_work_order_priority",
        "work_order",
        "priority IN ('urgent_critical','urgent','normal','low')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_work_order_priority", "work_order", type_="check")
    op.drop_column("work_order", "priority")
