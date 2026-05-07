"""sprint 16.3 v1.5 — 律所→平台介绍费账单

Revision ID: 19003v15
Revises: 19002v15
Create Date: 2026-05-06 21:00:00.000000

按月聚合 LegalConversionOrder.platform_fee_amount → 律所应付账单。
唯一约束 (law_firm_id, period_start, period_end) 防重复生成。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '19003v15'
down_revision: str | None = '19002v15'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'legal_platform_invoice',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('law_firm_id', sa.BigInteger(), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('order_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('invoice_lines', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='DRAFT'),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('payment_proof_url', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('DRAFT','CONFIRMED','PAID','CANCELLED')",
            name='ck_legal_invoice_status',
        ),
        sa.ForeignKeyConstraint(['law_firm_id'], ['law_firm.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'law_firm_id', 'period_start', 'period_end',
            name='uq_legal_invoice_firm_period',
        ),
    )
    op.create_index('ix_legal_platform_invoice_law_firm_id', 'legal_platform_invoice', ['law_firm_id'])
    op.create_index('ix_legal_invoice_firm_status', 'legal_platform_invoice', ['law_firm_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_legal_invoice_firm_status', table_name='legal_platform_invoice')
    op.drop_index('ix_legal_platform_invoice_law_firm_id', table_name='legal_platform_invoice')
    op.drop_table('legal_platform_invoice')
