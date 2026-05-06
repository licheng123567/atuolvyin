"""sprint 14.2 v1.3 — dial-start: heartbeat 字段 + 并发唯一约束 (PRD §10.1 / §11)

Revision ID: 17002v13
Revises: 17001v13
Create Date: 2026-05-06 14:00:00.000000

变更：
  1. call_record 加 last_heartbeat_at TIMESTAMPTZ — agent App 30s 一次心跳，超时清理任务用
  2. 唯一部分索引 uq_active_call_per_caller — 防同一 caller 并发拨号
     `CREATE UNIQUE INDEX uq_active_call_per_caller ON call_record(caller_user_id) WHERE status IN ('dialing','live')`
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '17002v13'
down_revision: str | None = '17001v13'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'call_record',
        sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True),
    )
    # 部分唯一索引：同一 caller 同时只能有一通 active call
    op.execute(
        "CREATE UNIQUE INDEX uq_active_call_per_caller "
        "ON call_record (caller_user_id) "
        "WHERE status IN ('dialing','live')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_active_call_per_caller")
    op.drop_column('call_record', 'last_heartbeat_at')
