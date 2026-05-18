"""易保全接入 — blockchain_config.app_key + blockchain_attestation 易保全字段

Revision ID: 24021v220g
Revises: 24020v220f
Create Date: 2026-05-18 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24021v220g"
down_revision: str | None = "24020v220f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "blockchain_config",
        sa.Column("app_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "blockchain_attestation",
        sa.Column("data_sha512", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "blockchain_attestation",
        sa.Column("provider_evidence_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "blockchain_attestation",
        sa.Column("preservation_id", sa.BigInteger(), nullable=True),
    )
    op.alter_column(
        "blockchain_attestation", "tx_hash", existing_type=sa.String(length=64), nullable=True
    )
    op.alter_column(
        "blockchain_attestation", "block_height", existing_type=sa.BigInteger(), nullable=True
    )


def downgrade() -> None:
    # 注意：若已存在易保全存证（tx_hash/block_height 为 NULL），下面的 NOT NULL 还原会失败 ——
    # 这是创建了 NULL 数据的迁移天然不可完全逆转的情形，downgrade 仅用于无数据的回滚。
    op.alter_column(
        "blockchain_attestation", "block_height", existing_type=sa.BigInteger(), nullable=False
    )
    op.alter_column(
        "blockchain_attestation", "tx_hash", existing_type=sa.String(length=64), nullable=False
    )
    op.drop_column("blockchain_attestation", "preservation_id")
    op.drop_column("blockchain_attestation", "provider_evidence_id")
    op.drop_column("blockchain_attestation", "data_sha512")
    op.drop_column("blockchain_config", "app_key")
