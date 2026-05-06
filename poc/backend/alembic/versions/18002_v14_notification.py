"""sprint 15.4 v1.4 — notification 表（站内信通道，PRD §L412）

Revision ID: 18002v14
Revises: 18001v14
Create Date: 2026-05-06 18:00:00.000000

让 Sprint 12.3 的通知规则真触发：本表是 system 渠道的落点。
SMS / 企微 / 钉钉 渠道无 schema 改动，靠服务层 webhook 调用。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '18002v14'
down_revision: str | None = '18001v14'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'notification',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('severity', sa.String(16), nullable=False, server_default='info'),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("severity IN ('info','warn','critical')", name='ck_notification_severity'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user_account.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notification_tenant_id', 'notification', ['tenant_id'])
    op.create_index('ix_notification_user_id', 'notification', ['user_id'])
    op.create_index('ix_notification_user_unread', 'notification', ['user_id', 'read_at'])


def downgrade() -> None:
    op.drop_index('ix_notification_user_unread', table_name='notification')
    op.drop_index('ix_notification_user_id', table_name='notification')
    op.drop_index('ix_notification_tenant_id', table_name='notification')
    op.drop_table('notification')
