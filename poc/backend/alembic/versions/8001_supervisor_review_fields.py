"""add supervisor review fields to analysis_result

Revision ID: 8001supervisor
Revises: 1120fc740bba
Create Date: 2026-05-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8001supervisor'
down_revision: Union[str, None] = '1120fc740bba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'analysis_result',
        sa.Column('supervisor_quality', sa.Text(), nullable=True),
    )
    op.add_column(
        'analysis_result',
        sa.Column('supervisor_review_note', sa.Text(), nullable=True),
    )
    op.add_column(
        'analysis_result',
        sa.Column('supervisor_reviewed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'analysis_result',
        sa.Column(
            'supervisor_reviewed_by',
            sa.BigInteger(),
            sa.ForeignKey('user_account.id'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('analysis_result', 'supervisor_reviewed_by')
    op.drop_column('analysis_result', 'supervisor_reviewed_at')
    op.drop_column('analysis_result', 'supervisor_review_note')
    op.drop_column('analysis_result', 'supervisor_quality')
