"""Sprint 13.1 / v2.2 — 区块链存证服务（PRD §20.3）。

submit_attestation() 是唯一公开入口，按 active BlockchainConfig.provider 分发：
  - mock（无 active 配置 / provider≠ebaoquan / 未激活）：本地确定性 tx_hash + 自增 block_height。
  - ebaoquan：调易保全 createEvidenceHash，成功后 best-effort 补查保全备案号。
provider 失败永不抛异常 —— 落 status="failed" 记录 + 写回 BlockchainConfig.last_failure_*。
调用方负责 db.commit()。
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from decimal import Decimal

from app.core.crypto import decrypt_phone
from app.models.billing_pricing import BillingPricing
from app.models.blockchain_attestation import BlockchainAttestation
from app.models.platform import BlockchainConfig
from app.services import ebaoquan

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "mock"
MOCK_ENDPOINT = "https://mock.blockchain.local/v1/attest"

# data_type → 易保全证据类型（1图片/2文档/3音频/4视频/99其他）
_EBAOQUAN_TYPE = {
    "call_recording": "3",
    "transcript": "2",
    "analysis": "2",
    "evidence_bundle": "99",
}


def _resolve_cost(db: Session, data_type: str) -> Decimal | None:
    """v0.5.9 — 查 active BillingPricing 拿单价(evidence_bundle 走 per_case 价,
    其他走 per_attestation 价)。NULL 兼容 — 没配置 active 价时不冻结金额。"""
    pricing = db.execute(
        select(BillingPricing).where(BillingPricing.is_active.is_(True)).limit(1)
    ).scalar_one_or_none()
    if pricing is None:
        return None
    if data_type == "evidence_bundle":
        return pricing.blockchain_price_per_case_bundle
    return pricing.blockchain_price_per_attestation


def _resolve_config(db: Session) -> BlockchainConfig | None:
    """取最新一行 *启用中* 的 BlockchainConfig（未启用的配置一律视作未配置，落 mock）。"""
    return db.execute(
        select(BlockchainConfig)
        .where(BlockchainConfig.is_active.is_(True))
        .order_by(desc(BlockchainConfig.updated_at))
        .limit(1)
    ).scalar_one_or_none()


def _next_block_height(db: Session) -> int:
    """模拟自增 block_height —— mock 分支用，取 max+1。"""
    current = db.execute(
        select(func.coalesce(func.max(BlockchainAttestation.block_height), 0))
    ).scalar_one()
    return int(current) + 1


def _gen_tx_hash(provider: str, data_sha256: str, nonce: str) -> str:
    """生成确定性 + 唯一的 64 字符 tx_hash（mock 分支用）。"""
    h = hashlib.sha256()
    h.update(provider.encode())
    h.update(b":")
    h.update(data_sha256.encode())
    h.update(b":")
    h.update(nonce.encode())
    return h.hexdigest()


def _record_config_failure(config: BlockchainConfig, reason: str) -> None:
    """写回 BlockchainConfig.last_failure_*（随调用方的 commit 一并提交）。"""
    config.last_failure_at = datetime.now(UTC)
    config.last_failure_reason = reason[:500]


def submit_attestation(
    db: Session,
    *,
    tenant_id: int,
    data: bytes,
    data_type: str,
    title: str,
    description: str | None = None,
    payload_metadata: dict[str, Any] | None = None,
    call_id: int | None = None,
    legal_case_id: int | None = None,
) -> BlockchainAttestation:
    """同步"上链"并返回 attestation 记录。

    - data: 被存证数据的原始字节（须与写入 ZIP 的字节一致）。
    - data_type: call_recording / transcript / analysis / evidence_bundle。
    - title / description: 易保全证据名称 / 备注（内部各截断 50 字）。
    - provider 失败永不抛异常 —— 落 status="failed" 记录。
    - db.flush()，调用方负责 commit。
    """
    if not data:
        raise ValueError("data 不能为空")

    data_sha256 = hashlib.sha256(data).hexdigest()
    data_sha512 = hashlib.sha512(data).hexdigest()
    now = datetime.now(UTC)
    config = _resolve_config(db)

    use_ebaoquan = (
        config is not None and config.provider == "ebaoquan" and config.is_active
    )

    # v0.5.9 — 查单价(active BillingPricing);data_type 决定 per_case vs per_attestation
    cost_amount = _resolve_cost(db, data_type)

    if not use_ebaoquan:
        # ── mock 分支（行为与历史一致）──
        provider = config.provider if config is not None else DEFAULT_PROVIDER
        endpoint = config.api_endpoint if config is not None else MOCK_ENDPOINT
        nonce = secrets.token_hex(16)
        record = BlockchainAttestation(
            tenant_id=tenant_id,
            call_id=call_id,
            legal_case_id=legal_case_id,
            data_sha256=data_sha256,
            data_sha512=data_sha512,
            data_type=data_type,
            chain_provider=provider,
            chain_endpoint=endpoint,
            tx_hash=_gen_tx_hash(provider, data_sha256, nonce),
            block_height=_next_block_height(db),
            status="confirmed",
            submitted_at=now,
            confirmed_at=now,
            cost_amount=cost_amount,
            payload_metadata=payload_metadata,
        )
        db.add(record)
        db.flush()
        return record

    # ── 易保全分支 ──
    assert config is not None  # use_ebaoquan 已保证
    record = BlockchainAttestation(
        tenant_id=tenant_id,
        call_id=call_id,
        legal_case_id=legal_case_id,
        data_sha256=data_sha256,
        data_sha512=data_sha512,
        data_type=data_type,
        chain_provider="ebaoquan",
        chain_endpoint=config.api_endpoint,
        tx_hash=None,
        block_height=None,
        status="failed",
        submitted_at=now,
        confirmed_at=None,
        cost_amount=cost_amount,
        payload_metadata=dict(payload_metadata or {}),
    )

    if not config.app_key or not config.api_key_enc:
        record.payload_metadata["error"] = "ERR_BLOCKCHAIN_NOT_CONFIGURED"
        _record_config_failure(config, "ERR_BLOCKCHAIN_NOT_CONFIGURED")
        db.add(record)
        db.flush()
        return record

    try:
        app_key_secret = decrypt_phone(config.api_key_enc)
    except Exception:
        logger.exception("BlockchainConfig.api_key_enc 解密失败")
        record.payload_metadata["error"] = "ERR_BLOCKCHAIN_NOT_CONFIGURED"
        _record_config_failure(config, "ERR_BLOCKCHAIN_NOT_CONFIGURED")
        db.add(record)
        db.flush()
        return record

    hash_result = ebaoquan.create_evidence_hash(
        base_url=config.api_endpoint,
        app_key=config.app_key,
        app_key_secret=app_key_secret,
        file_hash=data_sha512,
        name=title[:50],
        description=(description or "")[:50],
        evidence_type=_EBAOQUAN_TYPE.get(data_type, "99"),
    )

    if not hash_result.ok or hash_result.evidence_id is None:
        reason = hash_result.error or "ERR_EBAOQUAN_FAILED"
        record.payload_metadata["error"] = reason
        _record_config_failure(config, reason)
        db.add(record)
        db.flush()
        return record

    record.status = "confirmed"
    record.confirmed_at = datetime.now(UTC)
    record.provider_evidence_id = hash_result.evidence_id

    # best-effort 补查保全备案号 —— 失败不降级 confirmed 状态
    detail = ebaoquan.query_evidence_detail(
        base_url=config.api_endpoint,
        app_key=config.app_key,
        app_key_secret=app_key_secret,
        evidence_id=hash_result.evidence_id,
    )
    if detail.ok and detail.preservation_id is not None:
        record.preservation_id = detail.preservation_id

    db.add(record)
    db.flush()
    return record
