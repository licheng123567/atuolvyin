"""sprint 16.2 v1.5 — 律所池 + 律师 + legal_conversion_order FK

Revision ID: 19002v15
Revises: 19001v15
Create Date: 2026-05-06 20:00:00.000000

新表：law_firm + law_firm_lawyer
扩展：legal_conversion_order 添加 law_firm_id / lawyer_id（保留原 free-text 字段做审计快照）
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '19002v15'
down_revision: str | None = '19001v15'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── law_firm ───────────────────────────────────────────────────
    op.create_table(
        'law_firm',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('license_no', sa.String(64), nullable=True),
        sa.Column('region', sa.String(64), nullable=True),
        sa.Column('contact_name', sa.String(120), nullable=True),
        sa.Column('contact_phone', sa.String(32), nullable=True),
        sa.Column('address', sa.String(300), nullable=True),
        sa.Column('specialties', sa.ARRAY(sa.Text()), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('accepting_orders', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('rating_avg', sa.Numeric(3, 2), nullable=False, server_default='5.00'),
        sa.Column('completed_orders', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('license_no', name='uq_law_firm_license_no'),
    )
    op.create_index('ix_law_firm_enabled', 'law_firm', ['enabled', 'accepting_orders'])

    # ── law_firm_lawyer ────────────────────────────────────────────
    op.create_table(
        'law_firm_lawyer',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('law_firm_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('license_no', sa.String(64), nullable=True),
        sa.Column('phone', sa.String(32), nullable=True),
        sa.Column('specialties', sa.ARRAY(sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['law_firm_id'], ['law_firm.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_law_firm_lawyer_law_firm_id', 'law_firm_lawyer', ['law_firm_id'])
    op.create_index('ix_law_firm_lawyer_active', 'law_firm_lawyer', ['law_firm_id', 'is_active'])

    # ── legal_conversion_order FK 扩展 ────────────────────────────
    op.add_column(
        'legal_conversion_order',
        sa.Column('law_firm_id', sa.BigInteger(), nullable=True),
    )
    op.add_column(
        'legal_conversion_order',
        sa.Column('lawyer_id', sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        'fk_legal_conv_law_firm', 'legal_conversion_order', 'law_firm',
        ['law_firm_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_legal_conv_lawyer', 'legal_conversion_order', 'law_firm_lawyer',
        ['lawyer_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index(
        'ix_legal_conv_law_firm_status',
        'legal_conversion_order', ['law_firm_id', 'status'],
    )


def downgrade() -> None:
    op.drop_index('ix_legal_conv_law_firm_status', table_name='legal_conversion_order')
    op.drop_constraint('fk_legal_conv_lawyer', 'legal_conversion_order', type_='foreignkey')
    op.drop_constraint('fk_legal_conv_law_firm', 'legal_conversion_order', type_='foreignkey')
    op.drop_column('legal_conversion_order', 'lawyer_id')
    op.drop_column('legal_conversion_order', 'law_firm_id')
    op.drop_index('ix_law_firm_lawyer_active', table_name='law_firm_lawyer')
    op.drop_index('ix_law_firm_lawyer_law_firm_id', table_name='law_firm_lawyer')
    op.drop_table('law_firm_lawyer')
    op.drop_index('ix_law_firm_enabled', table_name='law_firm')
    op.drop_table('law_firm')
