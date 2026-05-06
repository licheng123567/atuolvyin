"""sprint 16.1 v1.5 — 法务转化通道（PRD §20.4）

Revision ID: 19001v15
Revises: 18002v14
Create Date: 2026-05-06 19:00:00.000000

新表：
- legal_service_package：4 种服务包目录（律师函/诉前调解/小额诉讼/完整代理）
- legal_conversion_order：物业 → 服务包 → 律所撮合订单

种子：4 条平台默认服务包（tenant_id=NULL 全局可见）
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '19001v15'
down_revision: str | None = '18002v14'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── legal_service_package ─────────────────────────────────────
    op.create_table(
        'legal_service_package',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=True),
        sa.Column('slug', sa.String(64), nullable=False),
        sa.Column('package_type', sa.String(32), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('platform_fee_rate', sa.Numeric(5, 4), nullable=False, server_default='0.25'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "package_type IN ('lawyer_letter','mediation','small_claims','full_agency')",
            name='ck_legal_pkg_type',
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'slug', name='uq_legal_pkg_tenant_slug'),
    )
    op.create_index('ix_legal_service_package_tenant_id', 'legal_service_package', ['tenant_id'])

    # ── legal_conversion_order ────────────────────────────────────
    op.create_table(
        'legal_conversion_order',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('case_id', sa.BigInteger(), nullable=False),
        sa.Column('package_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
        sa.Column('price_quoted', sa.Numeric(10, 2), nullable=False),
        sa.Column('platform_fee_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('assigned_law_firm', sa.String(200), nullable=True),
        sa.Column('assigned_lawyer_name', sa.String(120), nullable=True),
        sa.Column('timeline_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('recommendation', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('cost_estimate', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('dispatched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','dispatched','in_service','completed','cancelled')",
            name='ck_legal_conv_status',
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['case_id'], ['collection_case.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['package_id'], ['legal_service_package.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['user_account.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_legal_conversion_order_tenant_id', 'legal_conversion_order', ['tenant_id'])
    op.create_index('ix_legal_conversion_order_case_id', 'legal_conversion_order', ['case_id'])
    op.create_index('ix_legal_conv_tenant_status', 'legal_conversion_order', ['tenant_id', 'status'])

    # ── 4 个平台默认服务包种子（PRD §20.4 价格表）─────────────────
    op.execute(
        """
        INSERT INTO legal_service_package
          (tenant_id, slug, package_type, name, description, price, platform_fee_rate, enabled, sort_order)
        VALUES
          (NULL, 'lawyer_letter', 'lawyer_letter', '律师函发送',
           '加盖律所公章的催款律师函 + 邮寄送达', 199.00, 0.30, TRUE, 10),
          (NULL, 'mediation', 'mediation', '诉前调解',
           '律师代发调解通知 + 电话协商', 399.00, 0.25, TRUE, 20),
          (NULL, 'small_claims', 'small_claims', '小额诉讼协助',
           '诉状准备 + 材料提交指导（物业公司自行出庭）', 599.00, 0.25, TRUE, 30),
          (NULL, 'full_agency', 'full_agency', '完整代理',
           '律师全程代理起诉至执行（成功分成）', 0.00, 0.20, TRUE, 40)
        """
    )


def downgrade() -> None:
    op.drop_index('ix_legal_conv_tenant_status', table_name='legal_conversion_order')
    op.drop_index('ix_legal_conversion_order_case_id', table_name='legal_conversion_order')
    op.drop_index('ix_legal_conversion_order_tenant_id', table_name='legal_conversion_order')
    op.drop_table('legal_conversion_order')
    op.drop_index('ix_legal_service_package_tenant_id', table_name='legal_service_package')
    op.drop_table('legal_service_package')
