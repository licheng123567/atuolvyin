"""Sprint 13.1 — 区块链存证服务（PRD §20.3 v1.1）。

抽象层：本服务对调用方暴露 `submit_attestation()`，返回 BlockchainAttestation
实例（含 tx_hash + block_height）。当前实现 mock provider — 不真实上链，
而是基于本地确定性算法生成 tx_hash + 自增 block_height，并落库。

后续接入蚂蚁链/至信链 SDK 时只需替换 `_submit_to_chain` 内部逻辑。
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.blockchain_attestation import BlockchainAttestation
from app.models.platform import BlockchainConfig

DEFAULT_PROVIDER = "mock"
MOCK_ENDPOINT = "https://mock.blockchain.local/v1/attest"


def _resolve_provider(db: Session) -> tuple[str, str | None]:
    """Active BlockchainConfig 优先；未配置时落到 mock provider。"""
    cfg = db.execute(
        select(BlockchainConfig).where(BlockchainConfig.is_active.is_(True)).limit(1)
    ).scalar_one_or_none()
    if cfg is None:
        return DEFAULT_PROVIDER, MOCK_ENDPOINT
    return cfg.provider, cfg.api_endpoint


def _next_block_height(db: Session) -> int:
    """模拟自增 block_height — 真实链上由网络决定，这里取 max+1。"""
    current = db.execute(
        select(func.coalesce(func.max(BlockchainAttestation.block_height), 0))
    ).scalar_one()
    return int(current) + 1


def _gen_tx_hash(provider: str, data_sha256: str, nonce: str) -> str:
    """生成确定性 + 唯一的 64 字符 tx_hash。

    `nonce` 由调用方提供（通常是 secrets.token_hex(16)），保证同一 data_sha256
    多次上链能产出不同 tx_hash（区块链上同一 hash 上多次也是新 tx）。
    """
    h = hashlib.sha256()
    h.update(provider.encode())
    h.update(b":")
    h.update(data_sha256.encode())
    h.update(b":")
    h.update(nonce.encode())
    return h.hexdigest()


def submit_attestation(
    db: Session,
    *,
    tenant_id: int,
    data_sha256: str,
    data_type: str,
    payload_metadata: dict[str, Any] | None = None,
    call_id: int | None = None,
    legal_case_id: int | None = None,
) -> BlockchainAttestation:
    """同步"上链"并返回 attestation 记录。

    - data_sha256: 被存证数据的 SHA-256（小写 hex）
    - data_type: call_recording / transcript / analysis / evidence_bundle
    - payload_metadata: 公开核验页可展示的非敏感元数据（call_id/case_id/tenant_name 等）
    - 调用方负责 db.commit()。
    """
    if len(data_sha256) != 64:
        raise ValueError("data_sha256 必须为 64 字符 hex")
    provider, endpoint = _resolve_provider(db)
    nonce = secrets.token_hex(16)
    tx_hash = _gen_tx_hash(provider, data_sha256, nonce)
    block_height = _next_block_height(db)
    now = datetime.now(UTC)

    record = BlockchainAttestation(
        tenant_id=tenant_id,
        call_id=call_id,
        legal_case_id=legal_case_id,
        data_sha256=data_sha256,
        data_type=data_type,
        chain_provider=provider,
        chain_endpoint=endpoint,
        tx_hash=tx_hash,
        block_height=block_height,
        status="confirmed",  # mock provider 立即确认；真实链需要 pending → confirmed
        submitted_at=now,
        confirmed_at=now,
        payload_metadata=payload_metadata,
    )
    db.add(record)
    db.flush()  # 让调用方拿到 record.id 而不必 commit
    return record
