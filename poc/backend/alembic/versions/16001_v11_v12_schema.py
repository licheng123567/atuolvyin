"""sprint 11/12/13 — v1.1 + v1.2 schema (8 new tables + risk_event disposition cols).

Revision ID: 16001v11
Revises: 15001super
Create Date: 2026-05-06 12:00:00.000000

新表（按 PRD 章节）：
  - dial_token (Sprint 12.1, PRD §10) — QR 拨号备份方案 token 表
  - tenant_settings (Sprint 8.5 + 12.3, PRD §3.14 / §L412) — 租户配置 + 通知规则
  - legal_document (Sprint 11.6, PRD §L2136) — 法务文件管理
  - customer_followup (Sprint 10.2, PRD §L2000) — 平台运营客户跟进
  - system_announcement (Sprint 10.3) — 系统公告
  - llm_prompt_template (Sprint 10.5) — 平台超管 LLM Prompt 模板
  - blockchain_config (Sprint 10.6) — 区块链合作方配置
  - blockchain_attestation (Sprint 13.1, PRD §20.3 v1.1) — 上链回执表

风控事件表新增 3 列（Sprint 9.4）：
  - risk_event.disposition_note / disposition_by / disposition_at
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '16001v11'
down_revision: str | None = '15001super'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── dial_token (Sprint 12.1) ──────────────────────────────
    op.create_table(
        'dial_token',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('call_id', sa.BigInteger(), nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['call_id'], ['call_record.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )

    # ── tenant_settings (Sprint 8.5 + 12.3) ───────────────────
    op.create_table(
        'tenant_settings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('recording_mode', sa.String(16), nullable=False, server_default='auto'),
        sa.Column('l3_hangup_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('contact_freq_max', sa.SmallInteger(), nullable=False, server_default='3'),
        sa.Column('retention_days', sa.Integer(), nullable=False, server_default='365'),
        # Sprint 12.3 — 通知规则
        sa.Column('notify_quota_warning', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('notify_script_disabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('notify_work_order_completed', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('notify_case_escalated', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('notify_promise_expiring', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            'notify_channels',
            postgresql.ARRAY(sa.String(16)),
            nullable=False,
            server_default=sa.text("ARRAY['system']::varchar[]"),
        ),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("recording_mode IN ('live','post','auto')", name='ck_tenant_settings_recording_mode'),
        sa.CheckConstraint('contact_freq_max BETWEEN 1 AND 30', name='ck_tenant_settings_freq'),
        sa.CheckConstraint('retention_days BETWEEN 30 AND 3650', name='ck_tenant_settings_retention'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id'),
    )

    # ── legal_document (Sprint 11.6) ──────────────────────────
    op.create_table(
        'legal_document',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('legal_case_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(32), nullable=False),
        sa.Column('object_key', sa.Text(), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('uploaded_by', sa.BigInteger(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "category IN ('contract','judgment','notice','evidence','other')",
            name='ck_legal_document_category',
        ),
        sa.ForeignKeyConstraint(['legal_case_id'], ['legal_case.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id']),
        sa.ForeignKeyConstraint(['uploaded_by'], ['user_account.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── customer_followup (Sprint 10.2) ───────────────────────
    op.create_table(
        'customer_followup',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('follow_up_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['user_account.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── system_announcement (Sprint 10.3) ─────────────────────
    op.create_table(
        'system_announcement',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('audience', sa.String(64), nullable=False),
        sa.Column('publish_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['user_account.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── llm_prompt_template (Sprint 10.5) ─────────────────────
    op.create_table(
        'llm_prompt_template',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['user_account.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'version', name='uq_llm_prompt_name_version'),
    )

    # ── blockchain_config (Sprint 10.6) ───────────────────────
    op.create_table(
        'blockchain_config',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('provider', sa.String(64), nullable=False),
        sa.Column('api_endpoint', sa.Text(), nullable=False),
        sa.Column('api_key_enc', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('last_failure_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_failure_reason', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', name='uq_blockchain_config_provider'),
    )

    # ── blockchain_attestation (Sprint 13.1) ──────────────────
    op.create_table(
        'blockchain_attestation',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('call_id', sa.BigInteger(), nullable=True),
        sa.Column('legal_case_id', sa.BigInteger(), nullable=True),
        sa.Column('data_sha256', sa.String(64), nullable=False),
        sa.Column('data_type', sa.String(32), nullable=False),
        sa.Column('chain_provider', sa.String(64), nullable=False),
        sa.Column('chain_endpoint', sa.Text(), nullable=True),
        sa.Column('tx_hash', sa.String(64), nullable=False),
        sa.Column('block_height', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('payload_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "status IN ('confirmed','failed','pending')",
            name='ck_blockchain_attestation_status',
        ),
        sa.CheckConstraint(
            "data_type IN ('call_recording','transcript','analysis','evidence_bundle')",
            name='ck_blockchain_attestation_data_type',
        ),
        sa.ForeignKeyConstraint(['call_id'], ['call_record.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['legal_case_id'], ['legal_case.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tx_hash'),
    )
    op.create_index(
        'ix_blockchain_attestation_tenant_id',
        'blockchain_attestation', ['tenant_id'],
    )
    op.create_index(
        'ix_blockchain_attestation_call_id',
        'blockchain_attestation', ['call_id'],
    )
    op.create_index(
        'ix_blockchain_attestation_tenant_call',
        'blockchain_attestation', ['tenant_id', 'call_id'],
    )

    # ── risk_event 新增 disposition 三列 (Sprint 9.4) ─────────
    op.add_column('risk_event', sa.Column('disposition_note', sa.Text(), nullable=True))
    op.add_column(
        'risk_event',
        sa.Column('disposition_by', sa.BigInteger(), nullable=True),
    )
    op.add_column(
        'risk_event',
        sa.Column('disposition_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_risk_event_disposition_by_user',
        'risk_event', 'user_account',
        ['disposition_by'], ['id'],
    )


def downgrade() -> None:
    # risk_event columns
    op.drop_constraint('fk_risk_event_disposition_by_user', 'risk_event', type_='foreignkey')
    op.drop_column('risk_event', 'disposition_at')
    op.drop_column('risk_event', 'disposition_by')
    op.drop_column('risk_event', 'disposition_note')

    # Tables (reverse order due to FKs)
    op.drop_index('ix_blockchain_attestation_tenant_call', table_name='blockchain_attestation')
    op.drop_index('ix_blockchain_attestation_call_id', table_name='blockchain_attestation')
    op.drop_index('ix_blockchain_attestation_tenant_id', table_name='blockchain_attestation')
    op.drop_table('blockchain_attestation')
    op.drop_table('blockchain_config')
    op.drop_table('llm_prompt_template')
    op.drop_table('system_announcement')
    op.drop_table('customer_followup')
    op.drop_table('legal_document')
    op.drop_table('tenant_settings')
    op.drop_table('dial_token')
