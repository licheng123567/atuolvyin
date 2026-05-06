"""Sprint 10 — Admin settlement management API tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.crypto import encrypt_phone


# ─── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def seeded_provider(db_session):
    """A service provider for contract testing."""
    from app.models.tenant import ServiceProvider
    p = ServiceProvider(
        name="测试律所",
        provider_type="legal",
        admin_phone_enc=encrypt_phone("13900000001"),
        is_active=True,
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def seeded_provider_contract(db_session, seeded_tenant, seeded_provider):
    """A provider-tenant contract bound to seeded_tenant."""
    from app.models.tenant import ProviderTenantContract
    contract = ProviderTenantContract(
        tenant_id=seeded_tenant.id,
        provider_id=seeded_provider.id,
        signed_at=datetime.now(timezone.utc),
        service_types=["legal"],
        status="active",
    )
    db_session.add(contract)
    db_session.flush()
    return contract


def _make_statement(
    db_session,
    contract_id: int,
    *,
    period_start: datetime,
    period_end: datetime,
    total_amount: Decimal = Decimal("12345.67"),
    status: str = "DRAFT",
):
    from app.models.settlement import SettlementStatement
    s = SettlementStatement(
        contract_id=contract_id,
        period_start=period_start,
        period_end=period_end,
        total_amount=total_amount,
        status=status,
    )
    db_session.add(s)
    db_session.flush()
    return s


@pytest.fixture
def seeded_settlement_draft(db_session, seeded_provider_contract):
    period_start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    period_end = datetime(2026, 4, 30, tzinfo=timezone.utc)
    return _make_statement(
        db_session,
        seeded_provider_contract.id,
        period_start=period_start,
        period_end=period_end,
    )


@pytest.fixture
def seeded_settlement_confirmed(db_session, seeded_provider_contract):
    period_start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    period_end = datetime(2026, 3, 31, tzinfo=timezone.utc)
    return _make_statement(
        db_session,
        seeded_provider_contract.id,
        period_start=period_start,
        period_end=period_end,
        status="CONFIRMED",
        total_amount=Decimal("888.00"),
    )


@pytest.fixture
def seeded_settlement_paid(db_session, seeded_provider_contract):
    period_start = datetime(2026, 2, 1, tzinfo=timezone.utc)
    period_end = datetime(2026, 2, 28, tzinfo=timezone.utc)
    s = _make_statement(
        db_session,
        seeded_provider_contract.id,
        period_start=period_start,
        period_end=period_end,
        status="PAID",
        total_amount=Decimal("500.00"),
    )
    s.paid_at = datetime.now(timezone.utc)
    s.payment_proof_url = "https://cdn.example.com/proof.jpg"
    db_session.flush()
    return s


# ─── tests ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_can_list_settlements(
    client, admin_auth_headers, seeded_settlement_draft, seeded_settlement_confirmed
):
    resp = await client.get(
        "/api/v1/admin/settlements", headers=admin_auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 2
    items = body["items"]
    ids = {i["id"] for i in items}
    assert seeded_settlement_draft.id in ids
    assert seeded_settlement_confirmed.id in ids
    # provider_name must appear
    sample = next(i for i in items if i["id"] == seeded_settlement_draft.id)
    assert sample["provider_name"] == "测试律所"


@pytest.mark.asyncio
async def test_filter_by_status_and_year_month(
    client, admin_auth_headers, seeded_settlement_draft, seeded_settlement_confirmed
):
    # Filter by status=CONFIRMED → only seeded_settlement_confirmed
    resp = await client.get(
        "/api/v1/admin/settlements?status=CONFIRMED",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(i["status"] == "CONFIRMED" for i in items)
    assert any(i["id"] == seeded_settlement_confirmed.id for i in items)

    # Filter by year_month=2026-04 → only the draft (period 2026-04)
    resp = await client.get(
        "/api/v1/admin/settlements?year_month=2026-04",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    ids = {i["id"] for i in resp.json()["items"]}
    assert seeded_settlement_draft.id in ids
    assert seeded_settlement_confirmed.id not in ids


@pytest.mark.asyncio
async def test_non_admin_forbidden(
    client, agent_auth_headers, supervisor_auth_headers, seeded_settlement_draft
):
    r1 = await client.get(
        "/api/v1/admin/settlements", headers=agent_auth_headers
    )
    assert r1.status_code == 403
    r2 = await client.get(
        "/api/v1/admin/settlements", headers=supervisor_auth_headers
    )
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_other_tenant_settlements_invisible(
    client, db_session, admin_auth_headers, seeded_settlement_draft
):
    """Statement under a different tenant must NOT appear in current tenant's list."""
    from app.models.tenant import (
        ProviderTenantContract,
        ServiceProvider,
        Tenant,
    )
    from app.models.settlement import SettlementStatement

    other_tenant = Tenant(
        name="另一物业",
        admin_phone_enc=encrypt_phone("13900099999"),
        plan="trial",
        is_active=True,
    )
    db_session.add(other_tenant)
    db_session.flush()
    other_provider = ServiceProvider(
        name="他家律所",
        provider_type="legal",
        admin_phone_enc=encrypt_phone("13900088888"),
        is_active=True,
    )
    db_session.add(other_provider)
    db_session.flush()
    other_contract = ProviderTenantContract(
        tenant_id=other_tenant.id,
        provider_id=other_provider.id,
        signed_at=datetime.now(timezone.utc),
        service_types=["legal"],
        status="active",
    )
    db_session.add(other_contract)
    db_session.flush()
    other_settle = SettlementStatement(
        contract_id=other_contract.id,
        period_start=datetime(2026, 4, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 4, 30, tzinfo=timezone.utc),
        total_amount=Decimal("9999.99"),
        status="DRAFT",
    )
    db_session.add(other_settle)
    db_session.flush()

    resp = await client.get(
        "/api/v1/admin/settlements", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    ids = {i["id"] for i in resp.json()["items"]}
    assert other_settle.id not in ids
    assert seeded_settlement_draft.id in ids

    # Detail of other tenant's statement → 404
    detail = await client.get(
        f"/api/v1/admin/settlements/{other_settle.id}",
        headers=admin_auth_headers,
    )
    assert detail.status_code == 404


@pytest.mark.asyncio
async def test_get_detail_includes_disputes(
    client, db_session, admin_auth_headers, seeded_settlement_draft, seeded_user
):
    from app.models.settlement import DisputeRecord
    rec = DisputeRecord(
        statement_id=seeded_settlement_draft.id,
        reason="金额对不上",
        status="open",
        submitted_by=seeded_user.id,
    )
    db_session.add(rec)
    db_session.flush()

    resp = await client.get(
        f"/api/v1/admin/settlements/{seeded_settlement_draft.id}",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == seeded_settlement_draft.id
    assert body["provider_name"] == "测试律所"
    assert isinstance(body["disputes"], list)
    assert len(body["disputes"]) == 1
    assert body["disputes"][0]["reason"] == "金额对不上"


@pytest.mark.asyncio
async def test_confirm_transitions_draft_to_confirmed(
    client, admin_auth_headers, seeded_settlement_draft
):
    resp = await client.patch(
        f"/api/v1/admin/settlements/{seeded_settlement_draft.id}/confirm",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "CONFIRMED"
    assert body["confirmed_at"] is not None


@pytest.mark.asyncio
async def test_confirm_rejects_non_draft(
    client, admin_auth_headers, seeded_settlement_confirmed
):
    resp = await client.patch(
        f"/api/v1/admin/settlements/{seeded_settlement_confirmed.id}/confirm",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_INVALID_TRANSITION"


@pytest.mark.asyncio
async def test_pay_transitions_confirmed_to_paid_and_stores_proof(
    client, admin_auth_headers, seeded_settlement_confirmed
):
    proof = "https://cdn.example.com/proof-xyz.jpg"
    resp = await client.patch(
        f"/api/v1/admin/settlements/{seeded_settlement_confirmed.id}/pay",
        headers=admin_auth_headers,
        json={"payment_proof_url": proof},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "PAID"
    assert body["payment_proof_url"] == proof
    assert body["paid_at"] is not None


@pytest.mark.asyncio
async def test_pay_rejects_non_confirmed(
    client, admin_auth_headers, seeded_settlement_draft
):
    resp = await client.patch(
        f"/api/v1/admin/settlements/{seeded_settlement_draft.id}/pay",
        headers=admin_auth_headers,
        json={},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_INVALID_TRANSITION"


@pytest.mark.asyncio
async def test_dispute_creates_record_and_changes_status(
    client, admin_auth_headers, seeded_settlement_draft, seeded_user
):
    resp = await client.post(
        f"/api/v1/admin/settlements/{seeded_settlement_draft.id}/dispute",
        headers=admin_auth_headers,
        json={"reason": "金额异常"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["statement_id"] == seeded_settlement_draft.id
    assert body["reason"] == "金额异常"
    assert body["status"] == "open"
    assert body["submitted_by"] == seeded_user.id

    # Statement should now be DISPUTED
    detail = await client.get(
        f"/api/v1/admin/settlements/{seeded_settlement_draft.id}",
        headers=admin_auth_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "DISPUTED"


@pytest.mark.asyncio
async def test_dispute_rejects_paid(
    client, admin_auth_headers, seeded_settlement_paid
):
    resp = await client.post(
        f"/api/v1/admin/settlements/{seeded_settlement_paid.id}/dispute",
        headers=admin_auth_headers,
        json={"reason": "已支付不可争议"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_INVALID_TRANSITION"
