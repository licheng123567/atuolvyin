"""v0.5.6 — provider_cases 服务商案件管理 API 测试。

覆盖:
- 列表只看到 Project.provider_id == 本服务商 的项目下的案件
- 跨 provider 的案件不出现
- 物业自办案件(Project.provider_id IS NULL)不出现
- 物业 admin token 调本端点 → 403(require_provider_roles 拒绝)
- 分配:给本服务商员工成功;给非本服务商员工 404 ERR_USER_NOT_IN_PROVIDER
- 分配:案件不在本服务商接手项目内 → 400 ERR_CROSS_PROVIDER
- 释放回公海:pool_type=public + assigned_to=None
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.core.crypto import encrypt_phone


# ─── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def seeded_provider2(db_session):
    """主测试服务商。"""
    from app.models.tenant import ServiceProvider

    p = ServiceProvider(
        name="v0.5.6 测试服务商 A",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13900056001"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def seeded_other_provider(db_session):
    """另一个服务商,用来验证 cross-provider 隔离。"""
    from app.models.tenant import ServiceProvider

    p = ServiceProvider(
        name="v0.5.6 测试服务商 B",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13900056002"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def seeded_provider2_admin(db_session, seeded_provider2, seeded_tenant):
    """provider2 的 admin 账号 + membership。"""
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        phone_enc=encrypt_phone("13900056010"),
        name="provider2 admin",
        password_hash=get_password_hash("Pa@1234567"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=user.id,
            tenant_id=seeded_tenant.id,
            role="admin",
            provider_id=seeded_provider2.id,
            is_active=True,
        )
    )
    db_session.flush()
    return user


@pytest.fixture
def seeded_provider2_agent(db_session, seeded_provider2, seeded_tenant):
    """provider2 的 agent 员工(可被分配案件)。"""
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        phone_enc=encrypt_phone("13900056020"),
        name="provider2 agent",
        password_hash=get_password_hash("Pa@1234567"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=user.id,
            tenant_id=seeded_tenant.id,
            role="agent",
            provider_id=seeded_provider2.id,
            is_active=True,
            work_mode="external",
        )
    )
    db_session.flush()
    return user


@pytest.fixture
def provider2_auth_headers(seeded_provider2_admin, seeded_provider2):
    from app.core.security import create_access_token

    token = create_access_token(
        {
            "sub": str(seeded_provider2_admin.id),
            "user_id": seeded_provider2_admin.id,
            "tenant_id": None,
            "role": "admin",
            "provider_id": seeded_provider2.id,
            "scope": f"provider:{seeded_provider2.id}",
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seeded_cases_3way(
    db_session, seeded_tenant, seeded_provider2, seeded_other_provider,
):
    """种 3 个项目 + 3 个案件:
    A. 项目 outsourced 给 provider2 → 案件 A(可见)
    B. 项目 outsourced 给 other_provider → 案件 B(不应可见)
    C. 物业自办项目(provider_id=NULL)→ 案件 C(不应可见)
    """
    from app.models.case import CollectionCase, OwnerProfile, Project

    project_a = Project(
        tenant_id=seeded_tenant.id, name="项目 A 外包给 provider2",
        provider_id=seeded_provider2.id, status="active",
    )
    project_b = Project(
        tenant_id=seeded_tenant.id, name="项目 B 外包给 other",
        provider_id=seeded_other_provider.id, status="active",
    )
    project_c = Project(
        tenant_id=seeded_tenant.id, name="项目 C 物业自办",
        provider_id=None, status="active",
    )
    db_session.add_all([project_a, project_b, project_c])
    db_session.flush()

    def make_owner(name: str, phone: str) -> OwnerProfile:
        o = OwnerProfile(
            tenant_id=seeded_tenant.id, name=name,
            phone_enc=encrypt_phone(phone), building="1", room="101",
        )
        db_session.add(o)
        db_session.flush()
        return o

    owner_a = make_owner("业主 A", "13800100001")
    owner_b = make_owner("业主 B", "13800100002")
    owner_c = make_owner("业主 C", "13800100003")

    case_a = CollectionCase(
        tenant_id=seeded_tenant.id, project_id=project_a.id, owner_id=owner_a.id,
        pool_type="public", stage="new", amount_owed=Decimal("1000"),
        months_overdue=2, priority_score=50,
    )
    case_b = CollectionCase(
        tenant_id=seeded_tenant.id, project_id=project_b.id, owner_id=owner_b.id,
        pool_type="public", stage="new", amount_owed=Decimal("2000"),
        months_overdue=3, priority_score=60,
    )
    case_c = CollectionCase(
        tenant_id=seeded_tenant.id, project_id=project_c.id, owner_id=owner_c.id,
        pool_type="public", stage="new", amount_owed=Decimal("3000"),
        months_overdue=4, priority_score=70,
    )
    db_session.add_all([case_a, case_b, case_c])
    db_session.flush()
    return {"a": case_a, "b": case_b, "c": case_c}


# ─── 列表 ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_only_own_provider_cases(
    client: AsyncClient, seeded_cases_3way, provider2_auth_headers,
):
    """provider2 admin 只看到 A,看不到 B(other_provider)/ C(物业自办)。"""
    resp = await client.get("/api/v1/provider/cases", headers=provider2_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    ids = {item["id"] for item in data["items"]}
    assert seeded_cases_3way["a"].id in ids
    assert seeded_cases_3way["b"].id not in ids
    assert seeded_cases_3way["c"].id not in ids


@pytest.mark.asyncio
async def test_list_rejects_tenant_admin(
    client: AsyncClient, seeded_cases_3way, admin_auth_headers,
):
    """物业 admin token(provider_id=None)调本端点 → 403。"""
    resp = await client.get("/api/v1/provider/cases", headers=admin_auth_headers)
    # require_provider_roles 守卫强制 provider_id 非空,物业 admin 拒绝
    assert resp.status_code == 403


# ─── 详情 ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detail_own_case_ok(
    client: AsyncClient, seeded_cases_3way, provider2_auth_headers,
):
    case_a_id = seeded_cases_3way["a"].id
    resp = await client.get(
        f"/api/v1/provider/cases/{case_a_id}", headers=provider2_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == case_a_id


@pytest.mark.asyncio
async def test_detail_other_provider_case_404(
    client: AsyncClient, seeded_cases_3way, provider2_auth_headers,
):
    """跨 provider 案件 → 404(故意不泄露存在性)。"""
    case_b_id = seeded_cases_3way["b"].id
    resp = await client.get(
        f"/api/v1/provider/cases/{case_b_id}", headers=provider2_auth_headers,
    )
    assert resp.status_code == 404


# ─── 分配 ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_assign_to_own_provider_agent_ok(
    client: AsyncClient,
    db_session,
    seeded_cases_3way,
    seeded_provider2_agent,
    provider2_auth_headers,
):
    case_a_id = seeded_cases_3way["a"].id
    resp = await client.post(
        "/api/v1/provider/cases/assign",
        json={"case_ids": [case_a_id], "assign_to": seeded_provider2_agent.id},
        headers=provider2_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["updated_count"] == 1

    from app.models.case import CollectionCase
    db_session.expire_all()
    refreshed = db_session.get(CollectionCase, case_a_id)
    assert refreshed.assigned_to == seeded_provider2_agent.id
    assert refreshed.pool_type == "private"


@pytest.mark.asyncio
async def test_assign_to_non_provider_user_rejected(
    client: AsyncClient, seeded_cases_3way, seeded_member_user, provider2_auth_headers,
):
    """目标用户不是本服务商成员 → 404 ERR_USER_NOT_IN_PROVIDER。"""
    case_a_id = seeded_cases_3way["a"].id
    resp = await client.post(
        "/api/v1/provider/cases/assign",
        json={"case_ids": [case_a_id], "assign_to": seeded_member_user.id},
        headers=provider2_auth_headers,
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body.get("code") == "ERR_USER_NOT_IN_PROVIDER" or body.get("detail", {}).get("code") == "ERR_USER_NOT_IN_PROVIDER"


@pytest.mark.asyncio
async def test_assign_cross_provider_case_rejected(
    client: AsyncClient,
    seeded_cases_3way,
    seeded_provider2_agent,
    provider2_auth_headers,
):
    """case_b 属于 other_provider 项目,不能被 provider2 admin 分配 → 400。"""
    case_b_id = seeded_cases_3way["b"].id
    resp = await client.post(
        "/api/v1/provider/cases/assign",
        json={"case_ids": [case_b_id], "assign_to": seeded_provider2_agent.id},
        headers=provider2_auth_headers,
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body.get("code") == "ERR_CROSS_PROVIDER" or body.get("detail", {}).get("code") == "ERR_CROSS_PROVIDER"


# ─── 释放回公海 ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_release_to_pool(
    client: AsyncClient,
    db_session,
    seeded_cases_3way,
    seeded_provider2_agent,
    provider2_auth_headers,
):
    """先分配 case_a 给 agent → 释放回公海 → assigned_to None + pool_type public。"""
    case_a = seeded_cases_3way["a"]
    case_a.assigned_to = seeded_provider2_agent.id
    case_a.pool_type = "private"
    db_session.commit()

    resp = await client.post(
        f"/api/v1/provider/cases/{case_a.id}/release",
        headers=provider2_auth_headers,
    )
    assert resp.status_code == 200

    from app.models.case import CollectionCase
    db_session.expire_all()
    refreshed = db_session.get(CollectionCase, case_a.id)
    assert refreshed.assigned_to is None
    assert refreshed.pool_type == "public"
