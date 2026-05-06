"""sprint 15 platform_super — audit_log + plan_config tables (with seed plans)

Revision ID: 15001super
Revises: 11001ops
Create Date: 2026-05-05 00:00:03.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '15001super'
down_revision: str | None = '11001ops'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── audit_log ─────────────────────────────────────────────
    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('actor_user_id', sa.BigInteger(), nullable=True),
        sa.Column('actor_role', sa.Text(), nullable=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=True),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('target_type', sa.Text(), nullable=True),
        sa.Column('target_id', sa.BigInteger(), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['actor_user_id'], ['user_account.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_log_action', 'audit_log', ['action'])
    op.create_index('ix_audit_log_created_at', 'audit_log', ['created_at'])
    op.create_index('ix_audit_log_actor_user_id', 'audit_log', ['actor_user_id'])
    op.create_index('ix_audit_log_tenant_id', 'audit_log', ['tenant_id'])

    # ── plan_config ───────────────────────────────────────────
    plan_config = op.create_table(
        'plan_config',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('plan_name', sa.Text(), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('monthly_minutes', sa.Integer(), nullable=False),
        sa.Column(
            'price_monthly',
            sa.Numeric(10, 2),
            server_default=sa.text('0'),
            nullable=False,
        ),
        sa.Column(
            'features',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            'is_active', sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_name', name='uq_plan_config_plan_name'),
    )

    # Seed default plans
    op.bulk_insert(
        plan_config,
        [
            {
                "plan_name": "trial",
                "display_name": "试用版",
                "monthly_minutes": 60,
                "price_monthly": 0,
                "features": {"realtime_assist": False, "script_library": False},
                "is_active": True,
            },
            {
                "plan_name": "basic",
                "display_name": "基础版",
                "monthly_minutes": 500,
                "price_monthly": 99,
                "features": {"realtime_assist": False, "script_library": True},
                "is_active": True,
            },
            {
                "plan_name": "standard",
                "display_name": "标准版",
                "monthly_minutes": 2000,
                "price_monthly": 299,
                "features": {"realtime_assist": True, "script_library": True},
                "is_active": True,
            },
            {
                "plan_name": "enterprise",
                "display_name": "企业版",
                "monthly_minutes": 10000,
                "price_monthly": 999,
                "features": {
                    "realtime_assist": True,
                    "script_library": True,
                    "audit_export": True,
                },
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table('plan_config')
    op.drop_index('ix_audit_log_tenant_id', table_name='audit_log')
    op.drop_index('ix_audit_log_actor_user_id', table_name='audit_log')
    op.drop_index('ix_audit_log_created_at', table_name='audit_log')
    op.drop_index('ix_audit_log_action', table_name='audit_log')
    op.drop_table('audit_log')
