"""Sprint 11.6 — legal_documents tests (PRD §L2136)."""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.fixture
def seeded_legal_case(db_session, seeded_tenant, seeded_case):
    from app.models.work import LegalCase

    lc = LegalCase(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        stage="evidence_collection",
        amount_disputed=Decimal("3000.00"),
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


def _upload_files_payload(name: str, content: bytes, mime: str = "application/pdf"):
    return {"file": (name, content, mime)}


# ── Upload ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_document_creates_record(
    client: AsyncClient, seeded_legal_case, legal_auth_headers
):
    resp = await client.post(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/documents",
        files=_upload_files_payload("contract.pdf", b"%PDF-1.4 fake"),
        data={"category": "contract"},
        headers=legal_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["category"] == "contract"
    assert data["name"] == "contract.pdf"
    assert data["size_bytes"] == len(b"%PDF-1.4 fake")
    assert data["mime_type"] == "application/pdf"
    assert data["uploaded_by_name"] is not None


@pytest.mark.asyncio
async def test_upload_document_custom_name(
    client: AsyncClient, seeded_legal_case, legal_auth_headers
):
    resp = await client.post(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/documents",
        files=_upload_files_payload("a.pdf", b"x"),
        data={"category": "judgment", "name": "（2026）京01民终123号判决书.pdf"},
        headers=legal_auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "（2026）京01民终123号判决书.pdf"


@pytest.mark.asyncio
async def test_upload_rejects_invalid_category(
    client: AsyncClient, seeded_legal_case, legal_auth_headers
):
    resp = await client.post(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/documents",
        files=_upload_files_payload("a.pdf", b"x"),
        data={"category": "weird-category"},
        headers=legal_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upload_rejects_invalid_mime(
    client: AsyncClient, seeded_legal_case, legal_auth_headers
):
    resp = await client.post(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/documents",
        files={"file": ("e.exe", b"\x4d\x5a binary", "application/x-msdownload")},
        data={"category": "evidence"},
        headers=legal_auth_headers,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "ERR_INVALID_MIME"


@pytest.mark.asyncio
async def test_upload_rejects_empty_file(
    client: AsyncClient, seeded_legal_case, legal_auth_headers
):
    resp = await client.post(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/documents",
        files=_upload_files_payload("empty.pdf", b""),
        data={"category": "other"},
        headers=legal_auth_headers,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "ERR_EMPTY_FILE"


@pytest.mark.asyncio
async def test_upload_unknown_legal_case_404(
    client: AsyncClient, legal_auth_headers
):
    resp = await client.post(
        "/api/v1/legal/cases/999999/documents",
        files=_upload_files_payload("a.pdf", b"x"),
        data={"category": "other"},
        headers=legal_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_requires_legal_role(
    client: AsyncClient, seeded_legal_case, agent_auth_headers
):
    resp = await client.post(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/documents",
        files=_upload_files_payload("a.pdf", b"x"),
        data={"category": "other"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 403


# ── List ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_documents_returns_uploaded(
    client: AsyncClient, seeded_legal_case, legal_auth_headers
):
    await client.post(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/documents",
        files=_upload_files_payload("a.pdf", b"a"),
        data={"category": "contract"},
        headers=legal_auth_headers,
    )
    await client.post(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/documents",
        files=_upload_files_payload("b.pdf", b"b"),
        data={"category": "judgment"},
        headers=legal_auth_headers,
    )
    resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/documents",
        headers=legal_auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    cats = {i["category"] for i in items}
    assert cats == {"contract", "judgment"}


@pytest.mark.asyncio
async def test_list_filter_by_category(
    client: AsyncClient, seeded_legal_case, legal_auth_headers
):
    for cat in ("contract", "judgment", "evidence"):
        await client.post(
            f"/api/v1/legal/cases/{seeded_legal_case.id}/documents",
            files=_upload_files_payload("x.pdf", b"x"),
            data={"category": cat},
            headers=legal_auth_headers,
        )
    resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/documents?category=judgment",
        headers=legal_auth_headers,
    )
    items = resp.json()
    assert len(items) == 1
    assert items[0]["category"] == "judgment"


# ── Download ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_download_url(
    client: AsyncClient, seeded_legal_case, legal_auth_headers
):
    up = await client.post(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/documents",
        files=_upload_files_payload("c.pdf", b"download-me"),
        data={"category": "contract"},
        headers=legal_auth_headers,
    )
    doc_id = up.json()["id"]
    resp = await client.get(
        f"/api/v1/legal/documents/{doc_id}/download",
        headers=legal_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["download_url"]
    assert data["name"] == "c.pdf"
    assert data["expires_in_sec"] == 3600


@pytest.mark.asyncio
async def test_download_unknown_404(
    client: AsyncClient, legal_auth_headers
):
    resp = await client.get(
        "/api/v1/legal/documents/999999/download",
        headers=legal_auth_headers,
    )
    assert resp.status_code == 404


# ── Soft delete ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_then_list_excludes(
    client: AsyncClient, seeded_legal_case, legal_auth_headers
):
    up = await client.post(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/documents",
        files=_upload_files_payload("d.pdf", b"d"),
        data={"category": "other"},
        headers=legal_auth_headers,
    )
    doc_id = up.json()["id"]

    delete = await client.delete(
        f"/api/v1/legal/documents/{doc_id}",
        headers=legal_auth_headers,
    )
    assert delete.status_code == 204

    listing = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/documents",
        headers=legal_auth_headers,
    )
    assert all(i["id"] != doc_id for i in listing.json())

    # Subsequent download returns 404 (since deleted_at set)
    dl = await client.get(
        f"/api/v1/legal/documents/{doc_id}/download",
        headers=legal_auth_headers,
    )
    assert dl.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_isolation(
    client: AsyncClient,
    db_session,
    seeded_member_user,
    legal_auth_headers,
):
    """Documents from tenant B can't be listed/downloaded by tenant A user."""
    from app.core.crypto import encrypt_phone
    from app.models.case import CollectionCase, OwnerProfile
    from app.models.legal_document import LegalDocument
    from app.models.tenant import Tenant
    from app.models.work import LegalCase

    other = Tenant(
        name="另一租户",
        admin_phone_enc=encrypt_phone("13900088001"),
        plan="trial",
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()
    o_owner = OwnerProfile(
        tenant_id=other.id,
        name="李四",
        phone_enc=encrypt_phone("13700000222"),
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
    o_doc = LegalDocument(
        tenant_id=other.id,
        legal_case_id=o_lc.id,
        name="other-tenant-doc.pdf",
        category="contract",
        object_key="legal_docs/other/abc.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        uploaded_by=seeded_member_user.id,
    )
    db_session.add(o_doc)
    db_session.flush()

    # tenant A legal user trying to list tenant B's case
    listing = await client.get(
        f"/api/v1/legal/cases/{o_lc.id}/documents",
        headers=legal_auth_headers,
    )
    assert listing.status_code == 404

    # tenant A legal user trying to download tenant B's doc
    dl = await client.get(
        f"/api/v1/legal/documents/{o_doc.id}/download",
        headers=legal_auth_headers,
    )
    assert dl.status_code == 404
