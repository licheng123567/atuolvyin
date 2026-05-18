"""Fix 3 (Bug2) — GET /api/v1/discount-policy 新端点（督导可读）。

端点不存在时 → 404；实现后督导 → 200 且返回 6 个字段；admin 也能访问。
"""
from __future__ import annotations

import pytest

from app.core.crypto import encrypt_phone

_EXPECTED_FIELDS = {
    "discount_auto_approve_threshold_pct",
    "discount_supervisor_max_pct",
    "discount_disabled",
    "late_fee_waive_auto_approve_threshold_pct",
    "late_fee_waive_supervisor_max_pct",
    "late_fee_waive_disabled",
}


@pytest.mark.asyncio
async def test_supervisor_can_read_discount_policy(
    client, supervisor_auth_headers
):
    """物业督导 GET /api/v1/discount-policy → 200，返回全部 6 个减免策略字段。"""
    resp = await client.get("/api/v1/discount-policy", headers=supervisor_auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert _EXPECTED_FIELDS.issubset(data.keys()), (
        f"缺少字段: {_EXPECTED_FIELDS - data.keys()}"
    )
    # 类型检查
    assert isinstance(data["discount_auto_approve_threshold_pct"], int)
    assert isinstance(data["discount_supervisor_max_pct"], int)
    assert isinstance(data["discount_disabled"], bool)
    assert isinstance(data["late_fee_waive_auto_approve_threshold_pct"], int)
    assert isinstance(data["late_fee_waive_supervisor_max_pct"], int)
    assert isinstance(data["late_fee_waive_disabled"], bool)


@pytest.mark.asyncio
async def test_admin_can_read_discount_policy(client, admin_auth_headers):
    """admin 也能读 discount-policy 端点。"""
    resp = await client.get("/api/v1/discount-policy", headers=admin_auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert _EXPECTED_FIELDS.issubset(data.keys())


@pytest.mark.asyncio
async def test_agent_cannot_read_discount_policy(client, agent_auth_headers):
    """agent 角色不在守卫列表 → 403。"""
    resp = await client.get("/api/v1/discount-policy", headers=agent_auth_headers)
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_provider_supervisor_cannot_read_discount_policy(
    client, db_session, seeded_tenant
):
    """服务商督导（provider_id 非 NULL）→ require_tenant_roles 拦 → 403。"""
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import ServiceProvider, UserTenantMembership
    from app.models.user import UserAccount

    provider = ServiceProvider(
        name="策略测试服务商",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13099881001"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(provider)
    db_session.flush()

    user = UserAccount(
        phone_enc=encrypt_phone("13099881002"),
        name="服务商督导",
        password_hash=get_password_hash("Sup@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=user.id,
            tenant_id=seeded_tenant.id,
            role="supervisor",
            provider_id=provider.id,
            is_active=True,
        )
    )
    db_session.flush()
    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": seeded_tenant.id,
            "role": "supervisor",
            "provider_id": provider.id,
            "scope": f"provider:{provider.id}",
        }
    )
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/api/v1/discount-policy", headers=headers)
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_discount_policy_returns_defaults_when_no_settings(
    client, supervisor_auth_headers
):
    """租户未配置 TenantSettings 时返回系统默认值（不 500）。"""
    resp = await client.get("/api/v1/discount-policy", headers=supervisor_auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # 检查默认值合理性（不为负数）
    assert data["discount_auto_approve_threshold_pct"] >= 0
    assert data["discount_supervisor_max_pct"] >= 0


@pytest.mark.asyncio
async def test_discount_policy_returns_custom_settings(
    client, db_session, seeded_tenant, supervisor_auth_headers
):
    """租户已配置 TenantSettings 时，端点回显实际配置值（而非默认值）。

    自定义值均满足模型 CHECK 约束：auto ≤ supervisor_max，各值 0-100。
    """
    from app.models.settings import TenantSettings

    settings = TenantSettings(
        tenant_id=seeded_tenant.id,
        discount_auto_approve_threshold_pct=15,
        discount_supervisor_max_pct=40,
        discount_disabled=True,
        late_fee_waive_auto_approve_threshold_pct=20,
        late_fee_waive_supervisor_max_pct=60,
        late_fee_waive_disabled=False,
    )
    db_session.add(settings)
    db_session.flush()

    resp = await client.get("/api/v1/discount-policy", headers=supervisor_auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["discount_auto_approve_threshold_pct"] == 15
    assert data["discount_supervisor_max_pct"] == 40
    assert data["discount_disabled"] is True
    assert data["late_fee_waive_auto_approve_threshold_pct"] == 20
    assert data["late_fee_waive_supervisor_max_pct"] == 60
    assert data["late_fee_waive_disabled"] is False
