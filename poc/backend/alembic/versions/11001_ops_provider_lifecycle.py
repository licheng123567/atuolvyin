"""sprint 11 ops — provider audit fields + tenant trial/disabled fields

Revision ID: 11001ops
Revises: 10001settle
Create Date: 2026-05-05 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '11001ops'
down_revision: Union[str, None] = '10001settle'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Tenant: trial flag + disabled audit ───────────────────
    op.add_column(
        'tenant',
        sa.Column(
            'is_trial', sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        'tenant',
        sa.Column('disabled_reason', sa.Text(), nullable=True),
    )
    op.add_column(
        'tenant',
        sa.Column('disabled_at', sa.DateTime(timezone=True), nullable=True),
    )

    # ── ServiceProvider: audit + descriptive fields ───────────
    op.add_column(
        'service_provider',
        sa.Column(
            'audit_status',
            sa.Text(),
            nullable=False,
            server_default='pending',
        ),
    )
    op.add_column(
        'service_provider',
        sa.Column('audit_reason', sa.Text(), nullable=True),
    )
    op.add_column(
        'service_provider',
        sa.Column('audit_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'service_provider',
        sa.Column('description', sa.Text(), nullable=True),
    )
    op.add_column(
        'service_provider',
        sa.Column('contact_email', sa.Text(), nullable=True),
    )

    op.create_check_constraint(
        'ck_service_provider_audit_status',
        'service_provider',
        "audit_status IN ('pending','approved','rejected')",
    )


def downgrade() -> None:
    op.drop_constraint(
        'ck_service_provider_audit_status',
        'service_provider',
        type_='check',
    )
    op.drop_column('service_provider', 'contact_email')
    op.drop_column('service_provider', 'description')
    op.drop_column('service_provider', 'audit_at')
    op.drop_column('service_provider', 'audit_reason')
    op.drop_column('service_provider', 'audit_status')

    op.drop_column('tenant', 'disabled_at')
    op.drop_column('tenant', 'disabled_reason')
    op.drop_column('tenant', 'is_trial')
