"""v0.5.4 — 加宽 legal_conversion_request.status 列(20 → 32)

新值 'approved_pending_legal' = 22 字符,超出原 String(20) 长度。

Revision ID: 24024v054b
Revises: 24023v054a
Create Date: 2026-05-19 23:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24024v054b"
down_revision: str | None = "24023v054a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "legal_conversion_request",
        "status",
        existing_type=sa.String(length=20),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    # 收窄回 20 前必须确保无超长值,否则报错
    op.execute(
        "UPDATE legal_conversion_request SET status = 'cancelled' "
        "WHERE length(status) > 20"
    )
    op.alter_column(
        "legal_conversion_request",
        "status",
        existing_type=sa.String(length=32),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
