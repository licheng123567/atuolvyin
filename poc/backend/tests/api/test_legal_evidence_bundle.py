"""Sprint 11.5 — legal evidence bundle ZIP download tests (PRD §L2135)."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient


# ── fixtures ─────────────────────────────────────────────────────────


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
            source_type="INTERNAL",
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


def _make_call_with_recording(
    db_session,
    tenant,
    case,
    member_user,
    *,
    audio_bytes: bytes,
    object_key: str | None = None,
    add_transcript: bool = True,
    add_analysis: bool = True,
):
    """Create a CallRecord + (optionally) Transcript + AnalysisResult and write
    audio bytes to LOCAL_STORAGE_ROOT so storage.get_bytes() can find them."""
    import uuid as _uuid

    from app.core.crypto import encrypt_phone
    from app.core.storage import storage
    from app.models.call import AnalysisResult, CallRecord, Transcript

    if object_key is None and audio_bytes:
        object_key = f"calls/{tenant.id}/{_uuid.uuid4().hex}.mp3"

    if object_key and audio_bytes:
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

    if add_transcript:
        db_session.add(
            Transcript(
                call_id=call.id,
                full_text="您好，您本月物业费 3000 元尚未缴纳。",
                segments=[
                    {"speaker": "agent", "start_ms": 0, "end_ms": 2000, "text": "您好"},
                    {"speaker": "owner", "start_ms": 2000, "end_ms": 5000, "text": "我知道了"},
                ],
                asr_model="mock",
            )
        )
    if add_analysis:
        db_session.add(
            AnalysisResult(
                call_id=call.id,
                summary="业主承诺本周末缴纳",
                key_segments={
                    "intent": "promise_pay",
                    "promise_date": "2026-05-09",
                    "promise_amount": 3000,
                },
                needs_review=False,
            )
        )
    db_session.flush()
    return call, object_key


# ── tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bundle_returns_zip_with_expected_artifacts(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_case,
    seeded_legal_case,
    seeded_member_user,
    legal_auth_headers,
):
    audio = b"fake-mp3-bytes-for-test-only"
    call, _ = _make_call_with_recording(
        db_session, seeded_tenant, seeded_case, seeded_member_user, audio_bytes=audio
    )

    resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = set(zf.namelist())
    base = f"case_{seeded_case.id}"
    assert f"{base}/bundle_manifest.json" in names
    assert f"{base}/case_summary.json" in names
    assert f"{base}/calls/call_{call.id}/recording.mp3" in names
    assert f"{base}/calls/call_{call.id}/transcript.txt" in names
    assert f"{base}/calls/call_{call.id}/transcript.segments.json" in names
    assert f"{base}/calls/call_{call.id}/analysis.json" in names
    assert f"{base}/calls/call_{call.id}/attestation.json" in names


@pytest.mark.asyncio
async def test_bundle_recording_bytes_match_storage(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_case,
    seeded_legal_case,
    seeded_member_user,
    legal_auth_headers,
):
    audio = b"\x00\x01\x02unique-recording-bytes\x03\x04"
    call, _ = _make_call_with_recording(
        db_session, seeded_tenant, seeded_case, seeded_member_user, audio_bytes=audio
    )
    resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    extracted = zf.read(f"case_{seeded_case.id}/calls/call_{call.id}/recording.mp3")
    assert extracted == audio


@pytest.mark.asyncio
async def test_bundle_attestation_includes_sha256(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_case,
    seeded_legal_case,
    seeded_member_user,
    legal_auth_headers,
):
    audio = b"sha256-test-payload"
    call, _ = _make_call_with_recording(
        db_session, seeded_tenant, seeded_case, seeded_member_user, audio_bytes=audio
    )
    resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    attestation = json.loads(
        zf.read(f"case_{seeded_case.id}/calls/call_{call.id}/attestation.json")
    )
    assert attestation["recording_sha256"] == hashlib.sha256(audio).hexdigest()
    assert attestation["call_id"] == call.id
    assert attestation["case_id"] == seeded_case.id
    assert attestation["recording_skipped"] is False


@pytest.mark.asyncio
async def test_bundle_skips_missing_transcript(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_case,
    seeded_legal_case,
    seeded_member_user,
    legal_auth_headers,
):
    call, _ = _make_call_with_recording(
        db_session,
        seeded_tenant,
        seeded_case,
        seeded_member_user,
        audio_bytes=b"audio",
        add_transcript=False,
        add_analysis=False,
    )
    resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    manifest = json.loads(
        zf.read(f"case_{seeded_case.id}/bundle_manifest.json")
    )
    transcript_entry = next(
        f for f in manifest["files"]
        if f["path"].endswith(f"call_{call.id}/transcript.txt")
    )
    assert transcript_entry.get("skipped") is True


@pytest.mark.asyncio
async def test_bundle_handles_call_without_recording(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_case,
    seeded_legal_case,
    seeded_member_user,
    legal_auth_headers,
):
    """A call with no object_key (e.g. failed upload) — bundle still completes
    and attestation marks recording as skipped."""
    call, _ = _make_call_with_recording(
        db_session,
        seeded_tenant,
        seeded_case,
        seeded_member_user,
        audio_bytes=b"",
        object_key=None,
    )
    resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    attestation = json.loads(
        zf.read(f"case_{seeded_case.id}/calls/call_{call.id}/attestation.json")
    )
    assert attestation["recording_skipped"] is True
    assert attestation["recording_sha256"] is None


@pytest.mark.asyncio
async def test_bundle_unknown_legal_case_404(
    client: AsyncClient, legal_auth_headers
):
    resp = await client.get(
        "/api/v1/legal/cases/999999/evidence-bundle",
        headers=legal_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bundle_cross_tenant_404(
    client: AsyncClient,
    db_session,
    legal_auth_headers,
    seeded_member_user,
):
    """A legal user from tenant A must not see tenant B's case."""
    from app.core.crypto import encrypt_phone
    from app.models.case import CollectionCase, OwnerProfile
    from app.models.tenant import Tenant
    from app.models.work import LegalCase

    other = Tenant(
        name="另一租户",
        admin_phone_enc=encrypt_phone("13900099001"),
        plan="trial",
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()
    o_owner = OwnerProfile(
        tenant_id=other.id,
        name="李四",
        phone_enc=encrypt_phone("13700000999"),
        building="2栋",
        room="201",
    )
    db_session.add(o_owner)
    db_session.flush()
    o_case = CollectionCase(
        tenant_id=other.id,
        owner_id=o_owner.id,
        pool_type="public",
        stage="new",
        amount_owed=Decimal("100.00"),
    )
    db_session.add(o_case)
    db_session.flush()
    o_lc = LegalCase(
        tenant_id=other.id,
        case_id=o_case.id,
        stage="evidence_collection",
    )
    db_session.add(o_lc)
    db_session.flush()

    resp = await client.get(
        f"/api/v1/legal/cases/{o_lc.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bundle_requires_legal_role(
    client: AsyncClient,
    seeded_legal_case,
    agent_auth_headers,
    admin_auth_headers,
):
    # agent rejected
    a = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=agent_auth_headers,
    )
    assert a.status_code == 403

    # admin allowed (LEGAL_ROLES = ("legal", "admin"))
    b = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=admin_auth_headers,
    )
    assert b.status_code == 200


@pytest.mark.asyncio
async def test_bundle_blockchain_unconfigured(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_case,
    seeded_legal_case,
    seeded_member_user,
    legal_auth_headers,
):
    call, _ = _make_call_with_recording(
        db_session, seeded_tenant, seeded_case, seeded_member_user, audio_bytes=b"x"
    )
    resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    attestation = json.loads(
        zf.read(f"case_{seeded_case.id}/calls/call_{call.id}/attestation.json")
    )
    assert attestation["blockchain"]["provider"] == "unconfigured"
    assert attestation["blockchain"]["status"] == "pending_chain"


@pytest.mark.asyncio
async def test_bundle_blockchain_active_provider(
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

    call, _ = _make_call_with_recording(
        db_session, seeded_tenant, seeded_case, seeded_member_user, audio_bytes=b"y"
    )
    resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    attestation = json.loads(
        zf.read(f"case_{seeded_case.id}/calls/call_{call.id}/attestation.json")
    )
    assert attestation["blockchain"]["provider"] == "antchain"
    assert attestation["blockchain"]["endpoint"].endswith("/attest")


@pytest.mark.asyncio
async def test_bundle_filename_format(
    client: AsyncClient, seeded_legal_case, legal_auth_headers, seeded_case
):
    resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    today = datetime.now(UTC).strftime("%Y%m%d")
    assert f"evidence_case_{seeded_case.id}_{today}.zip" in cd


@pytest.mark.asyncio
async def test_bundle_manifest_has_bundle_sha256(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_case,
    seeded_legal_case,
    seeded_member_user,
    legal_auth_headers,
):
    _make_call_with_recording(
        db_session, seeded_tenant, seeded_case, seeded_member_user, audio_bytes=b"abc"
    )
    resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    manifest = json.loads(
        zf.read(f"case_{seeded_case.id}/bundle_manifest.json")
    )
    assert manifest["bundle_version"] == "1.0"
    assert manifest["call_count"] == 1
    assert len(manifest["bundle_sha256"]) == 64  # SHA-256 hex
    assert manifest["tenant_id"] == seeded_tenant.id
