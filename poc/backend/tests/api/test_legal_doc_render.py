"""Sprint 16.4 — 法律文书自动生成 (PRD §20.4)."""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.fixture
def seeded_packages_4(db_session):
    from app.models.legal_conversion import LegalServicePackage
    pkgs = []
    for slug, ptype, name, price, fee_rate in [
        ("lawyer_letter", "lawyer_letter", "律师函发送", "199.00", "0.30"),
        ("mediation", "mediation", "诉前调解", "399.00", "0.25"),
        ("small_claims", "small_claims", "小额诉讼协助", "599.00", "0.25"),
        ("full_agency", "full_agency", "完整代理", "0.00", "0.20"),
    ]:
        p = LegalServicePackage(
            tenant_id=None, slug=slug, package_type=ptype,
            name=name, price=Decimal(price),
            platform_fee_rate=Decimal(fee_rate), sort_order=10,
        )
        db_session.add(p)
        pkgs.append(p)
    db_session.flush()
    return pkgs


@pytest.fixture
def seeded_doc_templates(db_session):
    """种 4 条平台默认模板（migration 在 testcontainers 下不会插入）。"""
    from app.models.legal_document_template import LegalDocumentTemplate
    tpls = []
    bodies = {
        "lawyer_letter": "致 {{owner_name}}：你欠 ¥{{amount_owed}}（{{months_overdue}}个月）。律所 {{firm_name}}，{{today_date}}。",
        "mediation": "{{owner_name}} 调解通知，律所 {{firm_name}}（{{lawyer_name}}），{{today_date}}。",
        "small_claims": "原告 {{tenant_name}} 诉 {{owner_name}}，标的 ¥{{amount_owed}}。",
        "full_agency": "委托 {{firm_name}} 全程代理 {{owner_name}} 案。",
    }
    for ptype, body in bodies.items():
        t = LegalDocumentTemplate(
            tenant_id=None, package_type=ptype, slug="default",
            title=f"{ptype} 模板", body_md=body,
        )
        db_session.add(t)
        tpls.append(t)
    db_session.flush()
    return tpls


@pytest.fixture
def seeded_firm_with_lawyer(db_session):
    from app.models.law_firm import LawFirm, LawFirmLawyer
    firm = LawFirm(name="北京金律律师事务所", license_no="LF-BJ-001", region="北京")
    db_session.add(firm)
    db_session.flush()
    lawyer = LawFirmLawyer(law_firm_id=firm.id, name="王律师")
    db_session.add(lawyer)
    db_session.flush()
    return firm, lawyer


# ── service: render_template_body ──────────────────────────────


def test_render_template_body_substitutes_vars():
    from app.services.legal_document_render import render_template_body
    body = render_template_body(
        "你好 {{name}}，欠款 {{amount}} 元",
        {"name": "张三", "amount": "1000"},
    )
    assert body == "你好 张三，欠款 1000 元"


def test_render_template_body_missing_var_falls_back():
    from app.services.legal_document_render import render_template_body
    body = render_template_body(
        "{{a}} 与 {{missing}} 之间",
        {"a": "X"},
    )
    assert body == "X 与 [未填] 之间"


# ── service: build_order_render_context ────────────────────────


def test_build_order_render_context_aggregates_fields(
    db_session, seeded_packages_4, seeded_case, seeded_firm_with_lawyer,
    admin_auth_headers, client: AsyncClient,
):
    """通过 API 创建订单后再聚合 context（间接测）。"""
    from app.models.legal_conversion import LegalConversionOrder
    from app.services.legal_document_render import build_order_render_context

    pkg = next(p for p in seeded_packages_4 if p.slug == "lawyer_letter")
    firm, lawyer = seeded_firm_with_lawyer
    order = LegalConversionOrder(
        tenant_id=seeded_case.tenant_id,
        case_id=seeded_case.id,
        package_id=pkg.id,
        status="dispatched",
        price_quoted=pkg.price,
        platform_fee_amount=pkg.price * pkg.platform_fee_rate,
        law_firm_id=firm.id,
        lawyer_id=lawyer.id,
        timeline_summary={"total_calls": 5},
    )
    db_session.add(order)
    db_session.flush()

    ctx = build_order_render_context(db_session, order=order)
    assert ctx["amount_owed"] == "3,000.00"  # seeded_case 默认 3000.00
    assert ctx["firm_name"] == "北京金律律师事务所"
    assert ctx["lawyer_name"] == "王律师"
    assert ctx["total_calls"] == 5
    assert "today_date" in ctx


# ── REST API: list templates ────────────────────────────────────


@pytest.mark.asyncio
async def test_list_doc_templates(
    client: AsyncClient, db_session, seeded_doc_templates, admin_auth_headers
):
    db_session.commit()
    resp = await client.get(
        "/api/v1/admin/legal-document-templates", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    pkg_types = {t["package_type"] for t in body}
    assert pkg_types == {"lawyer_letter", "mediation", "small_claims", "full_agency"}


# ── REST API: render document ──────────────────────────────────


@pytest.mark.asyncio
async def test_render_creates_v1_then_v2(
    client: AsyncClient, db_session, seeded_packages_4, seeded_doc_templates,
    seeded_case, admin_auth_headers,
):
    pkg = next(p for p in seeded_packages_4 if p.slug == "lawyer_letter")
    create = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": pkg.id},
        headers=admin_auth_headers,
    )
    order_id = create.json()["id"]

    r1 = await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/document",
        headers=admin_auth_headers,
    )
    assert r1.status_code == 201
    body1 = r1.json()
    assert body1["version"] == 1
    # Substitution worked: owner_name + amount_owed should be filled (no {{ }} left)
    assert "{{" not in body1["body_md"]
    assert "3,000.00" in body1["body_md"]  # seeded_case 默认欠费

    r2 = await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/document",
        headers=admin_auth_headers,
    )
    assert r2.status_code == 201
    assert r2.json()["version"] == 2

    versions = await client.get(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/document/versions",
        headers=admin_auth_headers,
    )
    assert versions.status_code == 200
    vers_body = versions.json()
    assert len(vers_body) == 2
    assert [v["version"] for v in vers_body] == [2, 1]  # desc


@pytest.mark.asyncio
async def test_get_latest_doc_404_before_render(
    client: AsyncClient, db_session, seeded_packages_4, seeded_doc_templates,
    seeded_case, admin_auth_headers,
):
    pkg = next(p for p in seeded_packages_4 if p.slug == "mediation")
    create = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": pkg.id},
        headers=admin_auth_headers,
    )
    order_id = create.json()["id"]
    resp = await client.get(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/document",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ERR_NO_RENDER"


@pytest.mark.asyncio
async def test_render_cross_tenant_404(
    client: AsyncClient, db_session, seeded_doc_templates, admin_auth_headers
):
    resp = await client.post(
        "/api/v1/admin/legal-conversion-orders/99999/document",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_render_uses_tenant_template_override(
    client: AsyncClient, db_session, seeded_packages_4, seeded_doc_templates,
    seeded_case, seeded_tenant, admin_auth_headers,
):
    """租户级模板（tenant_id=本租户）应当 override 平台默认。"""
    from app.models.legal_document_template import LegalDocumentTemplate

    db_session.add(LegalDocumentTemplate(
        tenant_id=seeded_tenant.id,
        package_type="lawyer_letter",
        slug="custom",
        title="自定义律师函",
        body_md="自定义版本：{{owner_name}} 欠 {{amount_owed}}",
    ))
    db_session.commit()

    pkg = next(p for p in seeded_packages_4 if p.slug == "lawyer_letter")
    create = await client.post(
        f"/api/v1/admin/cases/{seeded_case.id}/convert-to-legal",
        json={"package_id": pkg.id},
        headers=admin_auth_headers,
    )
    order_id = create.json()["id"]
    resp = await client.post(
        f"/api/v1/admin/legal-conversion-orders/{order_id}/document",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "自定义律师函"
    assert resp.json()["body_md"].startswith("自定义版本：")
