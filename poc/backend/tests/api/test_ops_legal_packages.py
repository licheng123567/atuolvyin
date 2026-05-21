"""v0.5.5 — OPS 服务包目录后台 tests (PRD §20.4 「服务包定价归属」)。

覆盖:
- GET  /ops/legal-packages 列出全平台 4 档(含 disabled)
- PATCH /ops/legal-packages/{id} 改 price / description / platform_fee_rate
- 守卫:非 ops/superadmin → 403
- 守卫:租户专属价(tenant_id != NULL)不在管理范围 → 404
- 审计:成功改动写 AuditLog(action='ops.legal_package.patched')
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.fixture
def seeded_platform_package(db_session):
    """平台级服务包(tenant_id IS NULL)"""
    from app.models.legal_conversion import LegalServicePackage
    pkg = LegalServicePackage(
        tenant_id=None,
        slug="test-lawyer-letter",
        package_type="lawyer_letter",
        name="测试律师函",
        description="初始描述",
        price=Decimal("800.00"),
        platform_fee_rate=Decimal("0.25"),
        enabled=True,
        sort_order=10,
    )
    db_session.add(pkg)
    db_session.flush()
    return pkg


@pytest.fixture
def seeded_tenant_package(db_session, seeded_tenant):
    """租户专属价(tenant_id 不为 NULL) — 不应被 OPS 目录管理"""
    from app.models.legal_conversion import LegalServicePackage
    pkg = LegalServicePackage(
        tenant_id=seeded_tenant.id,
        slug="tenant-special-letter",
        package_type="lawyer_letter",
        name="租户专属函",
        price=Decimal("999.00"),
        platform_fee_rate=Decimal("0.30"),
        enabled=True,
        sort_order=99,
    )
    db_session.add(pkg)
    db_session.flush()
    return pkg


# ── GET ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_packages_returns_only_platform_level(
    client: AsyncClient,
    seeded_platform_package,
    seeded_tenant_package,
    ops_auth_headers,
):
    resp = await client.get("/api/v1/ops/legal-packages", headers=ops_auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    slugs = {p["slug"] for p in items}
    assert "test-lawyer-letter" in slugs
    # 租户专属价被过滤
    assert "tenant-special-letter" not in slugs


@pytest.mark.asyncio
async def test_list_packages_forbidden_for_admin(
    client: AsyncClient, seeded_platform_package, admin_auth_headers
):
    resp = await client.get(
        "/api/v1/ops/legal-packages", headers=admin_auth_headers
    )
    # admin(物业)不是 ops/superadmin → require_roles 拒绝
    assert resp.status_code == 403


# ── PATCH ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_price_persists_and_audit_logged(
    client: AsyncClient,
    db_session,
    seeded_platform_package,
    ops_auth_headers,
):
    resp = await client.patch(
        f"/api/v1/ops/legal-packages/{seeded_platform_package.id}",
        headers=ops_auth_headers,
        json={"price": "950.00", "description": "新描述"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["price"]) == Decimal("950.00")
    assert data["description"] == "新描述"

    # 持久化校验
    from app.models.legal_conversion import LegalServicePackage
    db_session.expire_all()
    refreshed = db_session.get(LegalServicePackage, seeded_platform_package.id)
    assert refreshed.price == Decimal("950.00")
    assert refreshed.description == "新描述"

    # AuditLog 写入
    from sqlalchemy import select
    from app.models.audit import AuditLog
    logs = db_session.execute(
        select(AuditLog).where(AuditLog.action == "ops.legal_package.patched")
    ).scalars().all()
    assert any(l.target_id == seeded_platform_package.id for l in logs)


@pytest.mark.asyncio
async def test_patch_tenant_package_not_in_ops_scope(
    client: AsyncClient, seeded_tenant_package, ops_auth_headers
):
    resp = await client.patch(
        f"/api/v1/ops/legal-packages/{seeded_tenant_package.id}",
        headers=ops_auth_headers,
        json={"price": "1000.00"},
    )
    assert resp.status_code == 404
    # FastAPI 默认把 detail dict 平铺到 root,这里看 code
    body = resp.json()
    assert body.get("code") == "ERR_NOT_FOUND" or body.get("detail", {}).get("code") == "ERR_NOT_FOUND"


@pytest.mark.asyncio
async def test_patch_forbidden_for_admin(
    client: AsyncClient, seeded_platform_package, admin_auth_headers
):
    resp = await client.patch(
        f"/api/v1/ops/legal-packages/{seeded_platform_package.id}",
        headers=admin_auth_headers,
        json={"price": "500.00"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_patch_rate_must_be_between_0_and_1(
    client: AsyncClient, seeded_platform_package, ops_auth_headers
):
    resp = await client.patch(
        f"/api/v1/ops/legal-packages/{seeded_platform_package.id}",
        headers=ops_auth_headers,
        json={"platform_fee_rate": "1.5"},
    )
    assert resp.status_code == 422  # pydantic le=1 拒绝
