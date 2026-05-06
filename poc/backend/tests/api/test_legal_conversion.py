"""Sprint 16.1 — 法务转化通道（PRD §20.4）"""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def seeded_packages(db_session):
    """种 4 条平台默认服务包（migration 在 testcontainers 中不会跑 INSERT）。"""
    from app.models.legal_conversion import LegalServicePackage

    pkgs = [
        LegalServicePackage(
            tenant_id=None,
            slug="lawyer_letter",
            package_type="lawyer_letter",
            name="律师函发送",
            description="加盖律所公章的催款律师函 + 邮寄送达",
            price=Decimal("199.00"),
            platform_fee_rate=Decimal("0.30"),
            sort_order=10,
        ),
        LegalServicePackage(
            tenant_id=None,
            slug="mediation",
            package_type="mediation",
            name="诉前调解",
            description="律师代发调解通知 + 电话协商",
            price=Decimal("399.00"),
            platform_fee_rate=Decimal("0.25"),
            sort_order=20,
        ),
        LegalServicePackage(
            tenant_id=None,
            slug="small_claims",
            package_type="small_claims",
            name="小额诉讼协助",
            description="诉状准备 + 材料提交指导",
            price=Decimal("599.00"),
            platform_fee_rate=Decimal("0.25"),
            sort_order=30,
        ),
        LegalServicePackage(
            tenant_id=None,
            slug="full_agency",
            package_type="full_agency",
            name="完整代理",
            description="律师全程代理起诉至执行",
            price=Decimal("0.00"),
            platform_fee_rate=Decimal("0.20"),
            sort_order=40,
        ),
    ]
    for p in pkgs:
        db_session.add(p)
    db_session.flush()
    return pkgs


def _seed_admin(db_session, seeded_user, seeded_tenant):
    from app.models.tenant import UserTenantMembership
    db_session.add(UserTenantMembership(
        user_id=seeded_user.id,
        tenant_id=seeded_tenant.id,
        role="admin",
        source_type="INTERNAL",
        is_active=True,
    ))
    db_session.flush()


# ── Service-level: recommend / build_summary / cost_estimate ────


def test_recommend_lawyer_letter_for_small_amount():
    from app.services.legal_conversion import recommend_package

    rec = recommend_package(
        amount_owed=Decimal("250"), months_overdue=2, contact_count=2,
    )
    assert rec["slug"] == "lawyer_letter"


def test_recommend_small_claims_for_large_amount():
    from app.services.legal_conversion import recommend_package

    rec = recommend_package(
        amount_owed=Decimal("8000"), months_overdue=8, contact_count=6,
    )
    assert rec["slug"] == "small_claims"
    assert rec["confidence"] >= 0.85


def test_build_timeline_summary_aggregates_calls(
    db_session, seeded_case, seeded_tenant, seeded_user
):
    from datetime import UTC, datetime
    from app.models.call import CallRecord
    from app.services.legal_conversion import build_timeline_summary

    for i in range(3):
        db_session.add(CallRecord(
            tenant_id=seeded_tenant.id,
            case_id=seeded_case.id,
            caller_user_id=seeded_user.id,
            callee_phone_enc="dummy_enc",
            started_at=datetime(2026, 3, 1 + i, 10, 0, tzinfo=UTC),
            duration_sec=60,
            result_tag="无应答" if i == 0 else "拒接",
            status="ended",
        ))
    db_session.flush()

    summary = build_timeline_summary(db_session, case=seeded_case)
    assert summary["total_calls"] == 3
    assert summary["total_minutes"] == 3.0
    assert summary["result_tag_breakdown"].get("拒接") == 2


def test_estimate_cost_for_small_claims(seeded_packages):
    from app.services.legal_conversion import estimate_cost

    sc = next(p for p in seeded_packages if p.slug == "small_claims")
    cost = estimate_cost(package=sc, amount_owed=Decimal("8000"))
    assert cost["service_fee"] == 599.00
    assert cost["court_fee_estimate"] == 200.0  # 8000 * 0.025
    assert 0.7 < cost["recovery_probability"] < 0.8


# ── REST API ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_legal_packages(
    client: AsyncClient, db_session, seeded_user, seeded_tenant,
    seeded_packages, admin_auth_headers,
):
    resp = await client.get("/api/v1/admin/legal-packages", headers=admin_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    slugs = [p["slug"] for p in data]
    assert "lawyer_letter" in slugs
    assert "mediation" in slugs
    assert "small_claims" in slugs
    assert "full_agency" in slugs


@pytest.mark.asyncio
async def test_preview_case_conversion(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, admin_auth_headers,
):
    resp = await client.get(
        f"/api/v1/admin/cases/{seeded_case.id}/legal-conversion-preview",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "timeline_summary" in body
    assert body["recommendation"]["slug"] in {
        "lawyer_letter", "mediation", "small_claims", "full_agency",
    }
    assert len(body["available_packages"]) == 4


@pytest.mark.asyncio
async def test_convert_case_creates_order(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, admin_auth_headers,
):
    pkg = next(p for p in seeded_packages if p.slug == "mediation")
    resp = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": pkg.id, "notes": "多次催收无果"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["package_name"] == "诉前调解"
    assert Decimal(body["price_quoted"]) == Decimal("399.00")
    assert Decimal(body["platform_fee_amount"]) == Decimal("99.75")  # 399 * 0.25
    assert body["timeline_summary"] is not None
    assert body["recommendation"] is not None
    assert body["cost_estimate"] is not None


@pytest.mark.asyncio
async def test_convert_case_409_when_active_order_exists(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, admin_auth_headers,
):
    pkg = seeded_packages[0]
    r1 = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": pkg.id},
        headers=admin_auth_headers,
    )
    assert r1.status_code == 201
    r2 = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": pkg.id},
        headers=admin_auth_headers,
    )
    assert r2.status_code == 409
    assert r2.json()["code"] == "ERR_ORDER_EXISTS"


@pytest.mark.asyncio
async def test_convert_case_cross_tenant_404(
    client: AsyncClient, db_session, seeded_packages, admin_auth_headers,
):
    # 用 admin 角色（其他租户）访问不存在 case
    resp = await client.post(
        "/api/v1/admin/cases/99999/convert-to-legal",
        json={"package_id": seeded_packages[0].id},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_dispatch_and_complete_order(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, admin_auth_headers, ops_auth_headers,
):
    pkg = seeded_packages[0]
    create = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": pkg.id},
        headers=admin_auth_headers,
    )
    order_id = create.json()["id"]

    # admin 不能 dispatch（仅 ops）
    forbidden = await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/dispatch",
        json={"assigned_law_firm": "X 律所"},
        headers=admin_auth_headers,
    )
    assert forbidden.status_code == 403

    # ops 可以 dispatch
    disp = await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/dispatch",
        json={"assigned_law_firm": "金律律所", "assigned_lawyer_name": "王律师"},
        headers=ops_auth_headers,
    )
    assert disp.status_code == 200
    assert disp.json()["status"] == "dispatched"
    assert disp.json()["assigned_law_firm"] == "金律律所"

    # ops 标完成
    done = await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/complete",
        json={"notes": "已签收"},
        headers=ops_auth_headers,
    )
    assert done.status_code == 200
    assert done.json()["status"] == "completed"
    assert done.json()["completed_at"] is not None


@pytest.mark.asyncio
async def test_cancel_order(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, admin_auth_headers,
):
    pkg = seeded_packages[0]
    create = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": pkg.id},
        headers=admin_auth_headers,
    )
    order_id = create.json()["id"]

    cancel = await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/cancel",
        headers=admin_auth_headers,
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_list_orders_filters_by_status(
    client: AsyncClient, db_session, seeded_case, seeded_user, seeded_tenant,
    seeded_packages, admin_auth_headers,
):
    pkg = seeded_packages[0]
    await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": pkg.id},
        headers=admin_auth_headers,
    )
    listing = await client.get(
        "/api/v1/admin/legal-conversion-orders?status=pending",
        headers=admin_auth_headers,
    )
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] >= 1
    assert all(item["status"] == "pending" for item in body["items"])
