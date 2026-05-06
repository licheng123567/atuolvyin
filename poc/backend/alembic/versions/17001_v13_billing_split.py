"""sprint 14.1 v1.3 — 实时 vs 事后计费分离 (PRD §20.1.1)

Revision ID: 17001v13
Revises: 16001v11
Create Date: 2026-05-06 13:00:00.000000

变更：
  1. tenant_minute_usage 加 realtime_minutes / post_minutes（保留 used_minutes 为兼容总量）
  2. call_record 加 recording_mode VARCHAR(16) NOT NULL DEFAULT 'post' (CHECK ∈ live/post)
     — 在 dial-start 时按 TenantSettings.recording_mode 决议并冻结
  3. plan_config 加 monthly_realtime_minutes / monthly_post_minutes（NULL 表示不分别拦截）
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '17001v13'
down_revision: str | None = '16001v11'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── tenant_minute_usage 双字段 ────────────────────────────
    op.add_column(
        'tenant_minute_usage',
        sa.Column('realtime_minutes', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'tenant_minute_usage',
        sa.Column('post_minutes', sa.Integer(), nullable=False, server_default='0'),
    )
    # 历史 used_minutes 全部归并到 post_minutes（保守：旧记录视为事后模式）
    op.execute("UPDATE tenant_minute_usage SET post_minutes = used_minutes WHERE post_minutes = 0")

    # ── call_record.recording_mode ────────────────────────────
    op.add_column(
        'call_record',
        sa.Column('recording_mode', sa.String(16), nullable=False, server_default='post'),
    )
    op.create_check_constraint(
        'ck_call_record_recording_mode',
        'call_record',
        "recording_mode IN ('live','post')",
    )

    # ── plan_config 双配额字段 ────────────────────────────────
    op.add_column(
        'plan_config',
        sa.Column('monthly_realtime_minutes', sa.Integer(), nullable=True),
    )
    op.add_column(
        'plan_config',
        sa.Column('monthly_post_minutes', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('plan_config', 'monthly_post_minutes')
    op.drop_column('plan_config', 'monthly_realtime_minutes')
    op.drop_constraint('ck_call_record_recording_mode', 'call_record', type_='check')
    op.drop_column('call_record', 'recording_mode')
    op.drop_column('tenant_minute_usage', 'post_minutes')
    op.drop_column('tenant_minute_usage', 'realtime_minutes')
