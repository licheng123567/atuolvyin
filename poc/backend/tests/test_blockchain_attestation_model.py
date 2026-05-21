"""易保全接入 Task 1 — BlockchainConfig / BlockchainAttestation 模型列回归。"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.blockchain_attestation import BlockchainAttestation
from app.models.platform import BlockchainConfig


def test_blockchain_config_accepts_app_key(db_session):
    cfg = BlockchainConfig(
        provider="ebaoquan",
        api_endpoint="https://bs.sandbox.ebaoquan.org",
        app_key="a7ce728fbec40519",
        api_key_enc=None,
        is_active=True,
    )
    db_session.add(cfg)
    db_session.flush()
    db_session.refresh(cfg)
    assert cfg.app_key == "a7ce728fbec40519"


def test_attestation_allows_null_tx_hash_and_ebaoquan_fields(db_session, seeded_tenant):
    now = datetime.now(UTC)
    att = BlockchainAttestation(
        tenant_id=seeded_tenant.id,
        data_sha256="a" * 64,
        data_sha512="b" * 128,
        data_type="transcript",
        chain_provider="ebaoquan",
        chain_endpoint="https://bs.sandbox.ebaoquan.org",
        tx_hash=None,
        block_height=None,
        provider_evidence_id=96111,
        preservation_id=1852,
        status="confirmed",
        submitted_at=now,
        confirmed_at=now,
    )
    db_session.add(att)
    db_session.flush()
    db_session.refresh(att)
    assert att.tx_hash is None
    assert att.block_height is None
    assert att.provider_evidence_id == 96111
    assert att.preservation_id == 1852
    assert att.data_sha512 == "b" * 128


def test_two_null_tx_hash_rows_coexist(db_session, seeded_tenant):
    """易保全分支的多条 attestation tx_hash 均为 NULL —— Postgres 唯一约束允许多 NULL。"""
    now = datetime.now(UTC)

    def _make(data_sha: str) -> BlockchainAttestation:
        return BlockchainAttestation(
            tenant_id=seeded_tenant.id,
            data_sha256=data_sha,
            data_type="transcript",
            chain_provider="ebaoquan",
            tx_hash=None,
            block_height=None,
            status="confirmed",
            submitted_at=now,
        )

    db_session.add(_make("a" * 64))
    db_session.add(_make("c" * 64))
    db_session.flush()  # 不抛 IntegrityError 即通过


def test_duplicate_non_null_tx_hash_rejected(db_session, seeded_tenant):
    """非 NULL tx_hash 仍受唯一约束保护。"""
    now = datetime.now(UTC)

    def _make() -> BlockchainAttestation:
        return BlockchainAttestation(
            tenant_id=seeded_tenant.id,
            data_sha256="d" * 64,
            data_type="call_recording",
            chain_provider="mock",
            tx_hash="e" * 64,
            block_height=1,
            status="confirmed",
            submitted_at=now,
        )

    db_session.add(_make())
    db_session.flush()
    db_session.add(_make())
    with pytest.raises(IntegrityError):
        db_session.flush()
