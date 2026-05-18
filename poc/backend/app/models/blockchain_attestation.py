"""Sprint 13.1 — BlockchainAttestation (PRD §20.3 v1.1).

记录每次"上链"操作的回执：data_sha256 + 链上 tx_hash + block_height。
当前用 mock provider（chain_provider="mock"），生成本地确定性 tx_hash；
后续接入蚂蚁链/至信链 SDK 时替换 chain_provider 与 tx_hash 来源即可。

公开核验入口（GET /api/v1/public/verify/{tx_hash}）查询本表。
"""

from __future__ import annotations

from datetime import datetime
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
