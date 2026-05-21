"""易保全接入 Task 4 — submit_attestation mock/ebaoquan 分发测试。"""
from __future__ import annotations

from app.core.crypto import encrypt_phone
from app.models.platform import BlockchainConfig
from app.services import blockchain
from app.services.blockchain import submit_attestation
from app.services.ebaoquan import EbaoquanDetailResult, EbaoquanHashResult


def test_mock_branch_when_no_config(db_session, seeded_tenant):
    att = submit_attestation(
        db_session,
        tenant_id=seeded_tenant.id,
        data=b"recording-bytes",
        data_type="call_recording",
        title="案件1通话1录音",
    )
    assert att.status == "confirmed"
    assert att.chain_provider == "mock"
    assert att.tx_hash is not None and len(att.tx_hash) == 64
    assert att.block_height >= 1
    assert att.data_sha512 is not None and len(att.data_sha512) == 128


def test_mock_branch_when_non_ebaoquan_provider(db_session, seeded_tenant):
    db_session.add(
        BlockchainConfig(
            provider="antchain",
            api_endpoint="https://antchain.example/attest",
            is_active=True,
        )
    )
    db_session.flush()
    att = submit_attestation(
        db_session,
        tenant_id=seeded_tenant.id,
        data=b"x",
        data_type="transcript",
        title="t",
    )
    assert att.chain_provider == "antchain"
    assert att.tx_hash is not None


def test_ebaoquan_success(db_session, seeded_tenant, monkeypatch):
    db_session.add(
        BlockchainConfig(
            provider="ebaoquan",
            api_endpoint="https://bs.sandbox.ebaoquan.org",
            app_key="appkey1",
            api_key_enc=encrypt_phone("secret1"),
            is_active=True,
        )
    )
    db_session.flush()

    monkeypatch.setattr(
        blockchain.ebaoquan,
        "create_evidence_hash",
        lambda **kw: EbaoquanHashResult(ok=True, evidence_id=96111),
    )
    monkeypatch.setattr(
        blockchain.ebaoquan,
        "query_evidence_detail",
        lambda **kw: EbaoquanDetailResult(ok=True, preservation_id=1852),
    )
    att = submit_attestation(
        db_session,
        tenant_id=seeded_tenant.id,
        data=b"recording-bytes",
        data_type="call_recording",
        title="案件1通话1录音",
    )
    assert att.status == "confirmed"
    assert att.chain_provider == "ebaoquan"
    assert att.tx_hash is None
    assert att.block_height is None
    assert att.provider_evidence_id == 96111
    assert att.preservation_id == 1852


def test_ebaoquan_success_but_detail_lookup_fails(db_session, seeded_tenant, monkeypatch):
    db_session.add(
        BlockchainConfig(
            provider="ebaoquan",
            api_endpoint="https://bs.sandbox.ebaoquan.org",
            app_key="appkey1",
            api_key_enc=encrypt_phone("secret1"),
            is_active=True,
        )
    )
    db_session.flush()
    monkeypatch.setattr(
        blockchain.ebaoquan,
        "create_evidence_hash",
        lambda **kw: EbaoquanHashResult(ok=True, evidence_id=96111),
    )
    monkeypatch.setattr(
        blockchain.ebaoquan,
        "query_evidence_detail",
        lambda **kw: EbaoquanDetailResult(ok=False, error="ERR_EBAOQUAN_HTTP"),
    )
    att = submit_attestation(
        db_session,
        tenant_id=seeded_tenant.id,
        data=b"x",
        data_type="analysis",
        title="t",
    )
    assert att.status == "confirmed"
    assert att.provider_evidence_id == 96111
    assert att.preservation_id is None


def test_ebaoquan_create_failure_records_config_failure(db_session, seeded_tenant, monkeypatch):
    cfg = BlockchainConfig(
        provider="ebaoquan",
        api_endpoint="https://bs.sandbox.ebaoquan.org",
        app_key="appkey1",
        api_key_enc=encrypt_phone("secret1"),
        is_active=True,
    )
    db_session.add(cfg)
    db_session.flush()
    monkeypatch.setattr(
        blockchain.ebaoquan,
        "create_evidence_hash",
        lambda **kw: EbaoquanHashResult(ok=False, error="name 不正确"),
    )
    att = submit_attestation(
        db_session,
        tenant_id=seeded_tenant.id,
        data=b"x",
        data_type="transcript",
        title="t",
    )
    assert att.status == "failed"
    db_session.refresh(cfg)
    assert cfg.last_failure_at is not None
    assert "name 不正确" in cfg.last_failure_reason


def test_ebaoquan_decrypt_failure_marks_not_configured(db_session, seeded_tenant):
    """api_key_enc 存在但解密失败 → failed + ERR_BLOCKCHAIN_NOT_CONFIGURED。"""
    cfg = BlockchainConfig(
        provider="ebaoquan",
        api_endpoint="https://bs.sandbox.ebaoquan.org",
        app_key="appkey1",
        api_key_enc="非法密文不是有效AES",  # 解密必然失败
        is_active=True,
    )
    db_session.add(cfg)
    db_session.flush()
    att = submit_attestation(
        db_session,
        tenant_id=seeded_tenant.id,
        data=b"x",
        data_type="call_recording",
        title="t",
    )
    assert att.status == "failed"
    assert att.payload_metadata.get("error") == "ERR_BLOCKCHAIN_NOT_CONFIGURED"
    db_session.refresh(cfg)
    assert cfg.last_failure_reason == "ERR_BLOCKCHAIN_NOT_CONFIGURED"


def test_ebaoquan_active_but_missing_credentials(db_session, seeded_tenant):
    cfg = BlockchainConfig(
        provider="ebaoquan",
        api_endpoint="https://bs.sandbox.ebaoquan.org",
        app_key=None,
        api_key_enc=None,
        is_active=True,
    )
    db_session.add(cfg)
    db_session.flush()
    att = submit_attestation(
        db_session,
        tenant_id=seeded_tenant.id,
        data=b"x",
        data_type="call_recording",
        title="t",
    )
    assert att.status == "failed"
    assert att.payload_metadata.get("error") == "ERR_BLOCKCHAIN_NOT_CONFIGURED"
    db_session.refresh(cfg)
    assert cfg.last_failure_reason == "ERR_BLOCKCHAIN_NOT_CONFIGURED"


def test_inactive_other_provider_does_not_shadow_active_ebaoquan(
    db_session, seeded_tenant, monkeypatch
):
    """启用中的 ebaoquan 配置不应被一条更新但未启用的 antchain 配置遮蔽。"""
    ebq = BlockchainConfig(
        provider="ebaoquan",
        api_endpoint="https://bs.sandbox.ebaoquan.org",
        app_key="appkey1",
        api_key_enc=encrypt_phone("secret1"),
        is_active=True,
    )
    db_session.add(ebq)
    db_session.flush()
    # 之后保存一条更新时间更晚、但未启用的 antchain 配置
    db_session.add(
        BlockchainConfig(
            provider="antchain",
            api_endpoint="https://antchain.example/attest",
            is_active=False,
        )
    )
    db_session.flush()

    monkeypatch.setattr(
        blockchain.ebaoquan,
        "create_evidence_hash",
        lambda **kw: EbaoquanHashResult(ok=True, evidence_id=96111),
    )
    monkeypatch.setattr(
        blockchain.ebaoquan,
        "query_evidence_detail",
        lambda **kw: EbaoquanDetailResult(ok=True, preservation_id=1852),
    )
    att = submit_attestation(
        db_session,
        tenant_id=seeded_tenant.id,
        data=b"x",
        data_type="call_recording",
        title="t",
    )
    assert att.chain_provider == "ebaoquan"
    assert att.provider_evidence_id == 96111
