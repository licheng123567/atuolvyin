"""Sprint 13 — Legal Case endpoints tests."""
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
        lawyer_name="王律师",
        law_firm="某某律师事务所",
        next_milestone="2026-06-01 立案",
        notes="案件已立案准备中",
    )
    db_session.add(lc)
    db_session.flush()
    return lc


@pytest.fixture
def legal_auth_headers(db_session, seeded_user, seeded_tenant):
    from app.core.security import create_access_token
    from app.models.tenant import UserTenantMembership

    membership = UserTenantMembership(
        user_id=seeded_user.id,
        tenant_id=seeded_tenant.id,
        role="legal",
        is_active=True,
    )
    db_session.add(membership)
    db_session.flush()
    token = create_access_token({
        "sub": str(seeded_user.id),
        "user_id": seeded_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "legal",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}


# ── List ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_legal_cases_returns_seeded(
    client: AsyncClient, seeded_legal_case, legal_auth_headers
):
    resp = await client.get("/api/v1/legal/cases", headers=legal_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(item["id"] == seeded_legal_case.id for item in data["items"])
    item = next(i for i in data["items"] if i["id"] == seeded_legal_case.id)
    assert item["stage"] == "evidence_collection"
    assert item["lawyer_name"] == "王律师"
    assert item["owner_name"] == "张三"
    assert item["owner_phone_masked"].startswith("137")


@pytest.mark.asyncio
async def test_list_legal_cases_filter_by_stage(
    client: AsyncClient,
    seeded_legal_case,
    legal_auth_headers,
    db_session,
    seeded_tenant,
    seeded_case,
):
    from app.models.work import LegalCase

    other = LegalCase(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        stage="closed_won",
    )
    db_session.add(other)
    db_session.flush()

    resp = await client.get(
        "/api/v1/legal/cases",
        params={"stage": "evidence_collection"},
        headers=legal_auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(i["stage"] == "evidence_collection" for i in items)
    assert any(i["id"] == seeded_legal_case.id for i in items)
    assert all(i["id"] != other.id for i in items)


# ── Detail ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_legal_case_detail_includes_collection_case(
    client: AsyncClient, seeded_legal_case, legal_auth_headers
):
    resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}", headers=legal_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == seeded_legal_case.id
    assert data["collection_case"] is not None
    assert data["collection_case"]["owner_name"] == "张三"
    assert data["collection_case"]["amount_owed"] == "3000.00"


# ── Create ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_legal_case_from_collection_case(
    client: AsyncClient, seeded_case, legal_auth_headers
):
    resp = await client.post(
        "/api/v1/legal/cases",
        json={
            "case_id": seeded_case.id,
            "stage": "pending_eval",
            "amount_disputed": "5000.00",
            "notes": "新立法务案件",
        },
        headers=legal_auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["case_id"] == seeded_case.id
    assert data["stage"] == "pending_eval"
    assert data["amount_disputed"] == "5000.00"


# ── Patch ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_legal_case_updates_stage_and_lawyer(
    client: AsyncClient, seeded_legal_case, legal_auth_headers
):
    resp = await client.patch(
        f"/api/v1/legal/cases/{seeded_legal_case.id}",
        json={
            "stage": "litigation_filed",
            "lawyer_name": "李律师",
            "next_milestone": "2026-07-01 开庭",
        },
        headers=legal_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["stage"] == "litigation_filed"
    assert data["lawyer_name"] == "李律师"
    assert data["next_milestone"] == "2026-07-01 开庭"


# ── Role guard ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_legal_endpoints_reject_other_roles(
    client: AsyncClient, seeded_legal_case, agent_auth_headers
):
    resp = await client.get(
        "/api/v1/legal/cases", headers=agent_auth_headers
    )
    assert resp.status_code == 403
