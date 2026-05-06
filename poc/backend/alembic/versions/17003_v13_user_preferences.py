"""sprint 14.3 v1.3 — UserAccount.preferences JSONB (PRD §8.2)

Revision ID: 17003v13
Revises: 17002v13
Create Date: 2026-05-06 15:00:00.000000

UserAccount 增 preferences JSONB 字段。
当前用途：app_intro_dismissed 标记（首次登录引导 modal 是否已关闭）。
未来扩展：UI 偏好、通知开关等。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '17003v13'
down_revision: str | None = '17002v13'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'user_account',
        sa.Column(
            'preferences',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column('user_account', 'preferences')
