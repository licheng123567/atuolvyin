"""sprint 15.1 v1.4 — active_session 表（多设备登录踢出 PRD §11.5）

Revision ID: 18001v14
Revises: 17003v13
Create Date: 2026-05-06 17:00:00.000000

每个 (user_id, device_type) 唯一一行，存当前 active 的 token_hash。
新设备登录时 upsert 覆盖旧 hash；老 token 后续请求 hash 不匹配 → 401 ERR_SESSION_EVICTED。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '18001v14'
down_revision: str | None = '17003v13'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'active_session',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('device_type', sa.String(8), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("device_type IN ('pc','app')", name='ck_active_session_device_type'),
        sa.ForeignKeyConstraint(['user_id'], ['user_account.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'device_type', name='uq_active_session_user_device'),
    )


def downgrade() -> None:
    op.drop_table('active_session')
