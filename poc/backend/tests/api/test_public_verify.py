"""Sprint 13.1 — public verify endpoint tests (PRD §20.3 v1.1)."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient


# ── fixtures (duplicated from test_legal_evidence_bundle.py) ──────────


@pytest.fixture
def seeded_legal_case(db_session, seeded_tenant, seeded_case):
    from app.models.work import LegalCase

    lc = LegalCase(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        stage="evidence_collection",
        amount_disputed=Decimal("3000.00"),
        lawyer_name="王律师",
        law_firm="阳光律师事务所",
        next_milestone="2026-06-01 立案",
    )
    db_session.add(lc)
    db_session.flush()
    return lc


@pytest.fixture
def legal_auth_headers(db_session, seeded_user, seeded_tenant):
    from app.core.security import create_access_token
    from app.models.tenant import UserTenantMembership

    db_session.add(
        UserTenantMembership(
            user_id=seeded_user.id,
            tenant_id=seeded_tenant.id,
            role="legal",
            is_active=True,
        )
    )
    db_session.flush()
    token = create_access_token({
        "sub": str(seeded_user.id),
        "user_id": seeded_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "legal",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}


def _make_call_with_recording(db_session, tenant, case, member_user, *, audio_bytes):
    import uuid as _uuid

    from app.core.crypto import encrypt_phone
    from app.core.storage import storage
    from app.models.call import AnalysisResult, CallRecord, Transcript

    object_key = f"calls/{tenant.id}/{_uuid.uuid4().hex}.mp3"
    storage.put_object(object_key, audio_bytes, "audio/mpeg")

    call = CallRecord(
        tenant_id=tenant.id,
        case_id=case.id,
        caller_user_id=member_user.id,
        callee_phone_enc=encrypt_phone("13700000001"),
        initiated_by="app",
        started_at=datetime.now(UTC) - timedelta(minutes=5),
        ended_at=datetime.now(UTC),
        duration_sec=120,
        billable_duration=110,
        object_key=object_key,
        recording_url="dummy",
        status="processed",
    )
    db_session.add(call)
    db_session.flush()
    db_session.add(Transcript(
        call_id=call.id,
        full_text="您好，您本月物业费 3000 元尚未缴纳。",
        segments=[],
        asr_model="mock",
    ))
    db_session.add(AnalysisResult(
        call_id=call.id,
        summary="业主承诺本周末缴纳",
        key_segments={"intent": "promise_pay"},
        needs_review=False,
    ))
    db_session.flush()
    return call, object_key


def _extract_first_tx_hash(zip_bytes: bytes, case_id: int) -> tuple[str, dict]:
    """Find the first call_*/attestation.json in the ZIP, return (tx_hash, full json)."""
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    for name in zf.namelist():
        if name.endswith("/attestation.json") and "/calls/" in name:
            data = json.loads(zf.read(name))
            tx = data["blockchain"]["transaction_id"]
            assert tx, "tx_hash must be populated for calls with recordings"
            return tx, data
    raise AssertionError(f"no attestation.json found in bundle for case {case_id}")


@pytest.mark.asyncio
async def test_verify_returns_attestation_after_bundle(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_case,
    seeded_legal_case,
    seeded_member_user,
    legal_auth_headers,
):
    call, _ = _make_call_with_recording(
        db_session, seeded_tenant, seeded_case, seeded_member_user,
        audio_bytes=b"verify-me",
    )
    bundle_resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    assert bundle_resp.status_code == 200
    tx_hash, attestation = _extract_first_tx_hash(bundle_resp.content, seeded_case.id)

    # No auth headers — verify endpoint is public
    resp = await client.get(f"/api/v1/public/verify/{tx_hash}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tx_hash"] == tx_hash
    assert data["data_sha256"] == attestation["recording_sha256"]
    assert data["data_type"] == "call_recording"
    assert data["status"] == "confirmed"
    assert data["chain_provider"] == "mock"
    assert data["block_height"] >= 1
    assert data["tenant_name"] == seeded_tenant.name
    assert data["call_id"] == call.id


@pytest.mark.asyncio
async def test_verify_unknown_tx_hash_returns_404(client: AsyncClient):
    bogus = "0" * 64
    resp = await client.get(f"/api/v1/public/verify/{bogus}")
    assert resp.status_code == 404
    assert resp.json()["code"] == "ERR_NOT_FOUND"


@pytest.mark.asyncio
async def test_verify_rejects_invalid_tx_hash_format(client: AsyncClient):
    # 63 chars (too short)
    resp = await client.get("/api/v1/public/verify/" + "a" * 63)
    assert resp.status_code == 422
    # non-hex char
    resp = await client.get("/api/v1/public/verify/" + "g" * 64)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_verify_does_not_leak_owner_phi(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_case,
    seeded_legal_case,
    seeded_member_user,
    seeded_owner,
    legal_auth_headers,
):
    """No business-sensitive PII in the public response (no owner name/phone/amount)."""
    _make_call_with_recording(
        db_session, seeded_tenant, seeded_case, seeded_member_user,
        audio_bytes=b"sensitive",
    )
    bundle_resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    tx_hash, _ = _extract_first_tx_hash(bundle_resp.content, seeded_case.id)
    resp = await client.get(f"/api/v1/public/verify/{tx_hash}")
    body = resp.text
    # Owner name and phone should NOT appear in public response
    assert seeded_owner.name not in body
    # Phone is encrypted in DB so it won't appear regardless, but assert key is absent
    data = resp.json()
    assert "owner_name" not in data
    assert "owner_phone" not in data
    assert "amount_owed" not in data


@pytest.mark.asyncio
async def test_verify_works_when_active_chain_provider_configured(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_case,
    seeded_legal_case,
    seeded_member_user,
    legal_auth_headers,
):
    from app.models.platform import BlockchainConfig

    db_session.add(
        BlockchainConfig(
            provider="antchain",
            api_endpoint="https://antchain.example/attest",
            api_key_enc=None,
            is_active=True,
        )
    )
    db_session.flush()

    _make_call_with_recording(
        db_session, seeded_tenant, seeded_case, seeded_member_user,
        audio_bytes=b"prod-chain",
    )
    bundle_resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    tx_hash, _ = _extract_first_tx_hash(bundle_resp.content, seeded_case.id)
    resp = await client.get(f"/api/v1/public/verify/{tx_hash}")
    assert resp.status_code == 200
    assert resp.json()["chain_provider"] == "antchain"
    assert resp.json()["chain_endpoint"] == "https://antchain.example/attest"
