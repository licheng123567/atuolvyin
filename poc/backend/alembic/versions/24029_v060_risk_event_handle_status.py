"""v0.6.0 — 风险事件处理状态字段

诱因:督导侧 EventDetailModal 长期是只读「v1.6 将开放完整处置流」占位。
本期开放完整处置流:督导可在弹窗内 select status + 写「处理结果」(已有
disposition_note 列)+ 提交;支持转培训 / 转法务路径。

变更:
1. risk_event.handle_status VARCHAR(32) NULL
   - 枚举:resolved / escalated / transferred_training / transferred_legal
   - NULL 表示「待处置」

Revision ID: 24029v060c
Revises: 24028v060b
Create Date: 2026-05-20 22:50:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24029v060c"
down_revision: str | None = "24028v060b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "risk_event",
        sa.Column("handle_status", sa.String(length=32), nullable=True),
    )
    op.create_check_constraint(
        "ck_risk_event_handle_status",
        "risk_event",
        "handle_status IS NULL OR handle_status IN "
        "('resolved','escalated','transferred_training','transferred_legal')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_risk_event_handle_status", "risk_event", type_="check")
    op.drop_column("risk_event", "handle_status")
