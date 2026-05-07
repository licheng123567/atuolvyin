"""Sprint 16.3 — 律所→平台介绍费账单 (PRD §20.4)."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.fixture
def seeded_packages(db_session):
    from app.models.legal_conversion import LegalServicePackage
    pkg = LegalServicePackage(
        tenant_id=None, slug="lawyer_letter", package_type="lawyer_letter",
        name="律师函发送", price=Decimal("199.00"),
        platform_fee_rate=Decimal("0.30"), sort_order=10,
    )
    db_session.add(pkg)
    db_session.flush()
    return [pkg]


@pytest.fixture
def seeded_firm(db_session):
    from app.models.law_firm import LawFirm
    firm = LawFirm(name="北京金律律师事务所", license_no="LF-BJ-001", region="北京")
    db_session.add(firm)
    db_session.flush()
    return firm


def _seed_completed_orders(
    db_session, *, tenant_id, case_id, firm_id, package_id, package_price,
    fee_amount, count, completed_at,
):
    """创建若干 completed 订单。"""
    from app.models.legal_conversion import LegalConversionOrder
    orders = []
    for _ in range(count):
        o = LegalConversionOrder(
            tenant_id=tenant_id,
            case_id=case_id,
            package_id=package_id,
            status="completed",
            price_quoted=package_price,
            platform_fee_amount=fee_amount,
            law_firm_id=firm_id,
            completed_at=completed_at,
        )
        db_session.add(o)
        orders.append(o)
    db_session.flush()
    return orders


# ── service ────────────────────────────────────────────────────


def test_aggregate_completed_orders_sums_within_period(
    db_session, seeded_packages, seeded_case, seeded_firm
):
    from app.services.legal_invoice import aggregate_completed_orders
    in_period = datetime(2026, 4, 15, 12, 0, tzinfo=UTC)
    out_period = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)

    _seed_completed_orders(
        db_session, tenant_id=seeded_case.tenant_id, case_id=seeded_case.id,
        firm_id=seeded_firm.id, package_id=seeded_packages[0].id,
        package_price=Decimal("199.00"),
        fee_amount=Decimal("59.70"), count=3, completed_at=in_period,
    )
    _seed_completed_orders(
        db_session, tenant_id=seeded_case.tenant_id, case_id=seeded_case.id,
        firm_id=seeded_firm.id, package_id=seeded_packages[0].id,
        package_price=Decimal("199.00"),
        fee_amount=Decimal("59.70"), count=2, completed_at=out_period,
    )

    total, lines = aggregate_completed_orders(
        db_session,
        law_firm_id=seeded_firm.id,
        period_start=datetime(2026, 4, 1, tzinfo=UTC),
        period_end=datetime(2026, 5, 1, tzinfo=UTC),
    )
    assert total == Decimal("179.10")  # 3 × 59.70
    assert len(lines) == 3


def test_generate_invoice_is_idempotent(
    db_session, seeded_packages, seeded_case, seeded_firm
):
    from app.services.legal_invoice import generate_invoice
    _seed_completed_orders(
        db_session, tenant_id=seeded_case.tenant_id, case_id=seeded_case.id,
        firm_id=seeded_firm.id, package_id=seeded_packages[0].id,
        package_price=Decimal("199.00"), fee_amount=Decimal("59.70"),
        count=2, completed_at=datetime(2026, 4, 10, tzinfo=UTC),
    )
    p_start = datetime(2026, 4, 1, tzinfo=UTC)
    p_end = datetime(2026, 5, 1, tzinfo=UTC)

    inv1, created1 = generate_invoice(
        db_session, law_firm_id=seeded_firm.id,
        period_start=p_start, period_end=p_end,
    )
    db_session.commit()
    assert created1 is True
    assert inv1.order_count == 2
    assert inv1.total_amount == Decimal("119.40")

    inv2, created2 = generate_invoice(
        db_session, law_firm_id=seeded_firm.id,
        period_start=p_start, period_end=p_end,
    )
    assert created2 is False
    assert inv2.id == inv1.id


# ── REST API ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_invoice_endpoint_creates_draft(
    client: AsyncClient, db_session, seeded_packages, seeded_case,
    seeded_firm, ops_auth_headers,
):
    _seed_completed_orders(
        db_session, tenant_id=seeded_case.tenant_id, case_id=seeded_case.id,
        firm_id=seeded_firm.id, package_id=seeded_packages[0].id,
        package_price=Decimal("199.00"), fee_amount=Decimal("59.70"),
        count=4, completed_at=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
    )
    db_session.commit()
    resp = await client.post(
        f"/api/v1/legal-workstation/firms/{seeded_firm.id}/invoices",
        json={
            "period_start": "2026-04-01T00:00:00+00:00",
            "period_end": "2026-05-01T00:00:00+00:00",
        },
        headers=ops_auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "DRAFT"
    assert body["order_count"] == 4
    assert Decimal(body["total_amount"]) == Decimal("238.80")
    assert len(body["invoice_lines"]) == 4


@pytest.mark.asyncio
async def test_generate_invoice_invalid_period_422(
    client: AsyncClient, seeded_firm, ops_auth_headers,
):
    resp = await client.post(
        f"/api/v1/legal-workstation/firms/{seeded_firm.id}/invoices",
        json={
            "period_start": "2026-05-01T00:00:00+00:00",
            "period_end": "2026-04-01T00:00:00+00:00",
        },
        headers=ops_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_confirm_then_paid_state_transitions(
    client: AsyncClient, db_session, seeded_packages, seeded_case,
    seeded_firm, ops_auth_headers,
):
    _seed_completed_orders(
        db_session, tenant_id=seeded_case.tenant_id, case_id=seeded_case.id,
        firm_id=seeded_firm.id, package_id=seeded_packages[0].id,
        package_price=Decimal("199.00"), fee_amount=Decimal("59.70"),
        count=1, completed_at=datetime(2026, 4, 10, tzinfo=UTC),
    )
    db_session.commit()
    create = await client.post(
        f"/api/v1/legal-workstation/firms/{seeded_firm.id}/invoices",
        json={
            "period_start": "2026-04-01T00:00:00+00:00",
            "period_end": "2026-05-01T00:00:00+00:00",
        },
        headers=ops_auth_headers,
    )
    invoice_id = create.json()["id"]

    confirm = await client.post(
        f"/api/v1/legal-workstation/invoices/{invoice_id}/confirm",
        json={},
        headers=ops_auth_headers,
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "CONFIRMED"
    assert confirm.json()["confirmed_at"] is not None

    paid = await client.post(
        f"/api/v1/legal-workstation/invoices/{invoice_id}/paid",
        json={"payment_proof_url": "https://oss/proof.png"},
        headers=ops_auth_headers,
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "PAID"
    assert paid.json()["payment_proof_url"] == "https://oss/proof.png"


@pytest.mark.asyncio
async def test_paid_skips_draft_409(
    client: AsyncClient, db_session, seeded_packages, seeded_case,
    seeded_firm, ops_auth_headers,
):
    _seed_completed_orders(
        db_session, tenant_id=seeded_case.tenant_id, case_id=seeded_case.id,
        firm_id=seeded_firm.id, package_id=seeded_packages[0].id,
        package_price=Decimal("199.00"), fee_amount=Decimal("59.70"),
        count=1, completed_at=datetime(2026, 4, 10, tzinfo=UTC),
    )
    db_session.commit()
    create = await client.post(
        f"/api/v1/legal-workstation/firms/{seeded_firm.id}/invoices",
        json={
            "period_start": "2026-04-01T00:00:00+00:00",
            "period_end": "2026-05-01T00:00:00+00:00",
        },
        headers=ops_auth_headers,
    )
    invoice_id = create.json()["id"]
    # 不先 confirm，直接标 PAID 应当 409
    resp = await client.post(
        f"/api/v1/legal-workstation/invoices/{invoice_id}/paid",
        json={},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_admin_role_cannot_access_invoices_403(
    client: AsyncClient, seeded_firm, admin_auth_headers,
):
    resp = await client.post(
        f"/api/v1/legal-workstation/firms/{seeded_firm.id}/invoices",
        json={
            "period_start": "2026-04-01T00:00:00+00:00",
            "period_end": "2026-05-01T00:00:00+00:00",
        },
        headers=admin_auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_firm_invoices_filters(
    client: AsyncClient, db_session, seeded_packages, seeded_case,
    seeded_firm, ops_auth_headers,
):
    _seed_completed_orders(
        db_session, tenant_id=seeded_case.tenant_id, case_id=seeded_case.id,
        firm_id=seeded_firm.id, package_id=seeded_packages[0].id,
        package_price=Decimal("199.00"), fee_amount=Decimal("59.70"),
        count=1, completed_at=datetime(2026, 4, 10, tzinfo=UTC),
    )
    db_session.commit()
    await client.post(
        f"/api/v1/legal-workstation/firms/{seeded_firm.id}/invoices",
        json={
            "period_start": "2026-04-01T00:00:00+00:00",
            "period_end": "2026-05-01T00:00:00+00:00",
        },
        headers=ops_auth_headers,
    )
    resp = await client.get(
        f"/api/v1/legal-workstation/firms/{seeded_firm.id}/invoices?status=DRAFT",
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(i["status"] == "DRAFT" for i in body["items"])


@pytest.mark.asyncio
async def test_firm_stats_includes_unpaid_total(
    client: AsyncClient, db_session, seeded_packages, seeded_case,
    seeded_firm, ops_auth_headers,
):
    _seed_completed_orders(
        db_session, tenant_id=seeded_case.tenant_id, case_id=seeded_case.id,
        firm_id=seeded_firm.id, package_id=seeded_packages[0].id,
        package_price=Decimal("199.00"), fee_amount=Decimal("59.70"),
        count=2, completed_at=datetime(2026, 4, 10, tzinfo=UTC),
    )
    db_session.commit()
    create = await client.post(
        f"/api/v1/legal-workstation/firms/{seeded_firm.id}/invoices",
        json={
            "period_start": "2026-04-01T00:00:00+00:00",
            "period_end": "2026-05-01T00:00:00+00:00",
        },
        headers=ops_auth_headers,
    )
    invoice_id = create.json()["id"]
    await client.post(
        f"/api/v1/legal-workstation/invoices/{invoice_id}/confirm",
        json={}, headers=ops_auth_headers,
    )
    stats = await client.get(
        f"/api/v1/legal-workstation/firms/{seeded_firm.id}/stats",
        headers=ops_auth_headers,
    )
    assert stats.status_code == 200
    body = stats.json()
    assert Decimal(str(body["platform_fee_unpaid"])) == Decimal("119.40")  # 2 × 59.70
