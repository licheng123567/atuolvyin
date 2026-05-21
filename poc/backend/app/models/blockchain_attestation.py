"""BlockchainAttestation —— 每次"上链"操作的回执（PRD §20.3）。

mock 分支：data_sha256 + 本地确定性 tx_hash + 自增 block_height。
易保全分支：data_sha512 + provider_evidence_id（evidenceId）+ preservation_id（保全备案号），
            tx_hash / block_height 留空。
分发逻辑见 app/services/blockchain.py 的 submit_attestation()。

公开核验入口 GET /api/v1/public/verify/{tx_hash} 仅服务 mock 分支记录；
易保全分支记录由易保全平台凭保全备案号核验。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BlockchainAttestation(Base):
    __tablename__ = "blockchain_attestation"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    call_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("call_record.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    legal_case_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("legal_case.id", ondelete="SET NULL"),
        nullable=True,
    )

    data_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    data_sha512: Mapped[str | None] = mapped_column(
        sa.String(128), nullable=True
    )  # 送易保全的 SHA-512 hex
    data_type: Mapped[str] = mapped_column(
        sa.String(32), nullable=False
    )  # "call_recording" / "transcript" / "analysis" / "evidence_bundle"

    chain_provider: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    chain_endpoint: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # mock 分支填本地 tx_hash + block_height；易保全分支留 NULL。
    tx_hash: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, unique=True)
    block_height: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    # 易保全分支字段
    provider_evidence_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, nullable=True
    )  # 易保全 evidenceId
    preservation_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, nullable=True
    )  # 易保全保全备案号

    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # "confirmed"/"failed"
    submitted_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    # v0.5.9 — 每次存证的快照费用(从 BillingPricing 读单价时冻结)。NULL 兼容
    # 老数据 / mock 调用未走计费的场景;月度 stats 时按 cost_amount IS NOT NULL 过滤。
    cost_amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 2), nullable=True)

    payload_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('confirmed','failed','pending')",
            name="ck_blockchain_attestation_status",
        ),
        sa.CheckConstraint(
            "data_type IN ('call_recording','transcript','analysis','evidence_bundle')",
            name="ck_blockchain_attestation_data_type",
        ),
        sa.Index("ix_blockchain_attestation_tenant_call", "tenant_id", "call_id"),
    )
