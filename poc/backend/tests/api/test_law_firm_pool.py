"""Sprint 16.2 — 律所池 + 法务工作台 (PRD §20.4)."""
from __future__ import annotations

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
    from app.models.law_firm import LawFirm, LawFirmLawyer
    firm = LawFirm(
        name="北京金律律师事务所",
        license_no="LF-BJ-001",
        region="北京",
        contact_name="王主任",
        contact_phone="010-88888888",
    )
    db_session.add(firm)
    db_session.flush()
    lawyer = LawFirmLawyer(
        law_firm_id=firm.id, name="王律师",
        license_no="A-2026-001", phone="13800001111",
    )
    db_session.add(lawyer)
    db_session.flush()
    return firm, lawyer


# ── ops_law_firms CRUD ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_and_list_law_firm(client: AsyncClient, ops_auth_headers):
    create = await client.post(
        "/api/v1/ops/law-firms",
        json={
            "name": "上海明德律所",
            "license_no": "LF-SH-002",
            "region": "上海",
            "contact_phone": "021-66666666",
            "specialties": ["合同法", "物业纠纷"],
        },
        headers=ops_auth_headers,
    )
    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "上海明德律所"
    assert body["enabled"] is True
    assert body["accepting_orders"] is True

    listing = await client.get("/api/v1/ops/law-firms", headers=ops_auth_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1


@pytest.mark.asyncio
async def test_create_law_firm_duplicate_license_409(
    client: AsyncClient, db_session, seeded_firm, ops_auth_headers
):
    resp = await client.post(
        "/api/v1/ops/law-firms",
        json={"name": "另一家律所", "license_no": "LF-BJ-001"},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_LICENSE_DUPLICATE"


@pytest.mark.asyncio
async def test_admin_cannot_create_law_firm_403(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.post(
        "/api/v1/ops/law-firms",
        json={"name": "X 律所"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_add_lawyer_to_firm(
    client: AsyncClient, db_session, seeded_firm, ops_auth_headers
):
    firm, _ = seeded_firm
    resp = await client.post(
        f"/api/v1/ops/law-firms/{firm.id}/lawyers",
        json={"name": "李律师", "license_no": "A-2026-002"},
        headers=ops_auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["law_firm_id"] == firm.id


@pytest.mark.asyncio
async def test_soft_delete_law_firm(
    client: AsyncClient, db_session, seeded_firm, ops_auth_headers
):
    firm, _ = seeded_firm
    resp = await client.delete(
        f"/api/v1/ops/law-firms/{firm.id}", headers=ops_auth_headers
    )
    assert resp.status_code == 204
    detail = await client.get(
        f"/api/v1/ops/law-firms/{firm.id}", headers=ops_auth_headers
    )
    body = detail.json()
    assert body["enabled"] is False
    assert body["accepting_orders"] is False


# ── dispatch with law_firm_id ───────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_with_law_firm_id_denormalizes_names(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, seeded_firm, admin_auth_headers, ops_auth_headers,
):
    firm, lawyer = seeded_firm
    create = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": seeded_packages[0].id},
        headers=admin_auth_headers,
    )
    order_id = create.json()["id"]

    disp = await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/dispatch",
        json={"law_firm_id": firm.id, "lawyer_id": lawyer.id},
        headers=ops_auth_headers,
    )
    assert disp.status_code == 200
    body = disp.json()
    assert body["status"] == "dispatched"
    assert body["assigned_law_firm"] == "北京金律律师事务所"
    assert body["assigned_lawyer_name"] == "王律师"


@pytest.mark.asyncio
async def test_dispatch_rejects_disabled_firm(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, seeded_firm, admin_auth_headers, ops_auth_headers,
):
    firm, _ = seeded_firm
    firm.accepting_orders = False
    db_session.commit()

    create = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": seeded_packages[0].id},
        headers=admin_auth_headers,
    )
    order_id = create.json()["id"]
    disp = await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/dispatch",
        json={"law_firm_id": firm.id},
        headers=ops_auth_headers,
    )
    assert disp.status_code == 400
    assert disp.json()["code"] == "ERR_FIRM_INVALID"


@pytest.mark.asyncio
async def test_dispatch_rejects_lawyer_from_different_firm(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, seeded_firm, admin_auth_headers, ops_auth_headers,
):
    from app.models.law_firm import LawFirm, LawFirmLawyer
    firm_a, lawyer_a = seeded_firm
    firm_b = LawFirm(name="其他律所", license_no="LF-OTH-001")
    db_session.add(firm_b)
    db_session.flush()

    create = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": seeded_packages[0].id},
        headers=admin_auth_headers,
    )
    order_id = create.json()["id"]
    disp = await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/dispatch",
        json={"law_firm_id": firm_b.id, "lawyer_id": lawyer_a.id},
        headers=ops_auth_headers,
    )
    assert disp.status_code == 400
    assert disp.json()["code"] == "ERR_LAWYER_INVALID"


@pytest.mark.asyncio
async def test_dispatch_freetext_fallback_still_works(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, admin_auth_headers, ops_auth_headers,
):
    create = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": seeded_packages[0].id},
        headers=admin_auth_headers,
    )
    order_id = create.json()["id"]
    disp = await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/dispatch",
        json={"assigned_law_firm": "临时合作律所"},
        headers=ops_auth_headers,
    )
    assert disp.status_code == 200
    assert disp.json()["assigned_law_firm"] == "临时合作律所"


@pytest.mark.asyncio
async def test_dispatch_missing_both_inputs_422(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, admin_auth_headers, ops_auth_headers,
):
    create = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": seeded_packages[0].id},
        headers=admin_auth_headers,
    )
    order_id = create.json()["id"]
    disp = await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/dispatch",
        json={},
        headers=ops_auth_headers,
    )
    assert disp.status_code == 422
    assert disp.json()["code"] == "ERR_VALIDATION"


# ── 法务工作台 ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workstation_lists_firm_orders(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, seeded_firm, admin_auth_headers, ops_auth_headers,
):
    firm, _ = seeded_firm
    create = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": seeded_packages[0].id},
        headers=admin_auth_headers,
    )
    order_id = create.json()["id"]
    await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/dispatch",
        json={"law_firm_id": firm.id},
        headers=ops_auth_headers,
    )

    resp = await client.get(
        f"/api/v1/legal-workstation/orders?law_firm_id={firm.id}",
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(o["assigned_law_firm"] == firm.name for o in body["items"])


@pytest.mark.asyncio
async def test_workstation_start_advances_to_in_service(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, seeded_firm, admin_auth_headers, ops_auth_headers,
):
    firm, _ = seeded_firm
    create = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": seeded_packages[0].id},
        headers=admin_auth_headers,
    )
    order_id = create.json()["id"]
    await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/dispatch",
        json={"law_firm_id": firm.id},
        headers=ops_auth_headers,
    )

    start = await client.post(
        f"/api/v1/legal-workstation/orders/{order_id}/start",
        headers=ops_auth_headers,
    )
    assert start.status_code == 200
    assert start.json()["status"] == "in_service"

    # 重复 start 应当 409
    start2 = await client.post(
        f"/api/v1/legal-workstation/orders/{order_id}/start",
        headers=ops_auth_headers,
    )
    assert start2.status_code == 409


@pytest.mark.asyncio
async def test_complete_increments_firm_completed_count(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, seeded_firm, admin_auth_headers, ops_auth_headers,
):
    firm, _ = seeded_firm
    initial = firm.completed_orders
    create = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": seeded_packages[0].id},
        headers=admin_auth_headers,
    )
    order_id = create.json()["id"]
    await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/dispatch",
        json={"law_firm_id": firm.id},
        headers=ops_auth_headers,
    )
    await client.post(
        f"/api/v1/legal-workstation/orders/{order_id}/start",
        headers=ops_auth_headers,
    )
    await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/complete",
        json={"notes": "已寄出"},
        headers=ops_auth_headers,
    )

    db_session.refresh(firm)
    assert firm.completed_orders == initial + 1


@pytest.mark.asyncio
async def test_workstation_firm_stats(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, seeded_firm, admin_auth_headers, ops_auth_headers,
):
    firm, _ = seeded_firm
    create = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": seeded_packages[0].id},
        headers=admin_auth_headers,
    )
    order_id = create.json()["id"]
    await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/dispatch",
        json={"law_firm_id": firm.id},
        headers=ops_auth_headers,
    )

    resp = await client.get(
        f"/api/v1/legal-workstation/firms/{firm.id}/stats",
        headers=ops_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["firm_id"] == firm.id
    assert body["by_status"].get("dispatched", 0) >= 1
