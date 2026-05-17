"""§9.2 Task 7 — D1 物业改内勤率 / D2 服务商改服务商率。"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.crypto import encrypt_phone


def _project(db_session, tenant_id, name, provider_id=None):
    from app.models.case import Project

    p = Project(tenant_id=tenant_id, name=name, provider_id=provider_id)
    db_session.add(p)
    db_session.flush()
    return p


def _provider_pm_headers(db_session, tenant_id, *, name_suffix, role="project_manager"):
    """造一个服务商 + 该服务商下 role 角色用户，返回 (headers, provider_id)。"""
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import ServiceProvider, UserTenantMembership
    from app.models.user import UserAccount

    provider = ServiceProvider(
        name=f"D2测试服务商{name_suffix}",
        provider_type="collection",
        admin_phone_enc=encrypt_phone(f"139000930{name_suffix}"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(provider)
    db_session.flush()
    user = UserAccount(
        phone_enc=encrypt_phone(f"139000931{name_suffix}"),
        name=f"服务商{role}{name_suffix}",
        password_hash=get_password_hash("Pm@12345678"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=user.id,
            tenant_id=tenant_id,
            role=role,
            provider_id=provider.id,
            work_mode="external" if role == "agent" else None,
            is_active=True,
        )
    )
    db_session.flush()
    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": None,
            "role": role,
            "provider_id": provider.id,
            "scope": f"provider:{provider.id}",
        }
    )
    return {"Authorization": f"Bearer {token}"}, provider.id


# ── D1：物业 PATCH 内勤率 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_d1_property_patch_internal_rate(
    client, db_session, seeded_tenant, admin_auth_headers
):
    project = _project(db_session, seeded_tenant.id, "D1 项目")
    resp = await client.patch(
        f"/api/v1/admin/projects/{project.id}",
        json={"internal_agent_commission_rate": "0.0700"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert Decimal(str(resp.json()["internal_agent_commission_rate"])) == Decimal("0.0700")
    db_session.refresh(project)
    assert project.internal_agent_commission_rate == Decimal("0.0700")


@pytest.mark.asyncio
async def test_d1_property_patch_cannot_set_provider_rate(
    client, db_session, seeded_tenant, admin_auth_headers
):
    """provider_agent_commission_rate 不在 ProjectUpdateIn — 物业 PATCH 传入被忽略。"""
    project = _project(db_session, seeded_tenant.id, "D1 越权项目")
    resp = await client.patch(
        f"/api/v1/admin/projects/{project.id}",
        json={"provider_agent_commission_rate": "0.9900"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    db_session.refresh(project)
    assert project.provider_agent_commission_rate is None


# ── D2：服务商 PATCH 服务商率 ────────────────────────────────────────


@pytest.mark.asyncio
async def test_d2_provider_patch_provider_rate(client, db_session, seeded_tenant):
    headers, provider_id = _provider_pm_headers(db_session, seeded_tenant.id, name_suffix="01")
    project = _project(db_session, seeded_tenant.id, "D2 项目", provider_id=provider_id)
    resp = await client.patch(
        f"/api/v1/provider/projects/{project.id}/commission-rate",
        json={"provider_agent_commission_rate": "0.1300"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    db_session.refresh(project)
    assert project.provider_agent_commission_rate == Decimal("0.1300")


@pytest.mark.asyncio
async def test_d2_cross_provider_404(client, db_session, seeded_tenant):
    headers_a, _provider_a = _provider_pm_headers(db_session, seeded_tenant.id, name_suffix="02")
    _headers_b, provider_b = _provider_pm_headers(db_session, seeded_tenant.id, name_suffix="03")
    # 项目属服务商 B，调用方是服务商 A
    project_b = _project(db_session, seeded_tenant.id, "B 的项目", provider_id=provider_b)
    resp = await client.patch(
        f"/api/v1/provider/projects/{project_b.id}/commission-rate",
        json={"provider_agent_commission_rate": "0.2000"},
        headers=headers_a,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ERR_NOT_FOUND"


@pytest.mark.asyncio
async def test_d2_property_side_token_403(client, db_session, seeded_tenant, admin_auth_headers):
    project = _project(db_session, seeded_tenant.id, "D2 物业越权项目")
    resp = await client.patch(
        f"/api/v1/provider/projects/{project.id}/commission-rate",
        json={"provider_agent_commission_rate": "0.2000"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_FORBIDDEN"


@pytest.mark.asyncio
async def test_d2_provider_agent_role_403(client, db_session, seeded_tenant):
    headers, provider_id = _provider_pm_headers(
        db_session, seeded_tenant.id, name_suffix="04", role="agent"
    )
    project = _project(db_session, seeded_tenant.id, "D2 角色越权项目", provider_id=provider_id)
    resp = await client.patch(
        f"/api/v1/provider/projects/{project.id}/commission-rate",
        json={"provider_agent_commission_rate": "0.2000"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_FORBIDDEN"
