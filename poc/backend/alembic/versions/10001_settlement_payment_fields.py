"""add payment_proof_url, confirmed_at, paid_at to settlement_statement

Revision ID: 10001settle
Revises: 8001supervisor
Create Date: 2026-05-05 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '10001settle'
down_revision: Union[str, None] = '8001supervisor'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'settlement_statement',
        sa.Column('payment_proof_url', sa.Text(), nullable=True),
    )
    op.add_column(
        'settlement_statement',
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'settlement_statement',
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('settlement_statement', 'paid_at')
    op.drop_column('settlement_statement', 'confirmed_at')
    op.drop_column('settlement_statement', 'payment_proof_url')
