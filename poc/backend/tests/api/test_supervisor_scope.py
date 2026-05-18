"""Task 1 — 共享 supervisor scope helper 单元测试。

测试场景：
- 物业侧督导（provider_id=None）能看到「无项目案件」+ 「物业项目案件」
- 物业侧督导看不到「服务商项目案件」
- 服务商侧督导只看到本服务商项目下的案件
- supervisor_agent_filter: 物业侧只看 provider_id IS NULL 的 agent
- supervisor_agent_filter: 服务商侧只看本服务商 agent
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.api._supervisor_scope import (
    SupervisorScope,
    resolve_call_provider_id,
    supervisor_agent_filter,
    supervisor_case_filter,
    supervisor_scope,
)
from app.models.case import CollectionCase, OwnerProfile, Project
from app.models.tenant import ServiceProvider, UserTenantMembership
from app.models.user import UserAccount

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(db_session, *, name: str, phone: str = "13900000099") -> ServiceProvider:
    from app.core.crypto import encrypt_phone

    prov = ServiceProvider(
        name=name,
        provider_type="collection",
        admin_phone_enc=encrypt_phone(phone),
    )
    db_session.add(prov)
    db_session.flush()
    return prov


def _make_project(db_session, tenant, *, name: str, provider_id: int | None) -> Project:
    proj = Project(
        tenant_id=tenant.id,
        name=name,
        provider_id=provider_id,
    )
    db_session.add(proj)
    db_session.flush()
    return proj


def _make_owner(db_session, tenant, *, name: str = "业主") -> OwnerProfile:
    from app.core.crypto import encrypt_phone

    owner = OwnerProfile(
        tenant_id=tenant.id,
        name=name,
        phone_enc=encrypt_phone("13811110000"),
        building="1栋",
        room="101",
    )
    db_session.add(owner)
    db_session.flush()
    return owner


def _make_case(
    db_session, tenant, owner, *, project_id: int | None
) -> CollectionCase:
    case = CollectionCase(
        tenant_id=tenant.id,
        project_id=project_id,
        owner_id=owner.id,
        pool_type="public",
        stage="new",
        amount_owed=Decimal("1000.00"),
    )
    db_session.add(case)
    db_session.flush()
    return case


_agent_phone_counter = 0


def _make_agent(
    db_session, tenant, *, name: str, provider_id: int | None
) -> UserTenantMembership:
    global _agent_phone_counter
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash

    _agent_phone_counter += 1
    # Use a counter to ensure unique phone numbers across tests within a session
    phone = f"138{_agent_phone_counter:08d}"
    user = UserAccount(
        name=name,
        phone_enc=encrypt_phone(phone),
        password_hash=get_password_hash("pw"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    mem = UserTenantMembership(
        tenant_id=tenant.id,
        user_id=user.id,
        role="agent",
        work_mode="internal" if provider_id is None else "external",
        provider_id=provider_id,
        is_active=True,
    )
    db_session.add(mem)
    db_session.flush()
    return mem


# ---------------------------------------------------------------------------
# Fixture: 建三类案件环境
# ---------------------------------------------------------------------------

@pytest.fixture()
def case_env(db_session, seeded_tenant):
    """
    建立以下数据：
    - provider_proj: 一个服务商项目（provider_id = provider.id）
    - property_proj: 一个物业自办项目（provider_id = None）
    - case_no_proj: 无项目案件（project_id = None）
    - case_property_proj: 物业项目案件
    - case_provider_proj: 服务商项目案件

    同时创建另一个租户（other_tenant）及其无关案件，确认 tenant 隔离。
    """
    provider = _make_provider(db_session, name="外呼服务商A", phone="13900000010")
    provider_proj = _make_project(
        db_session, seeded_tenant, name="服务商项目", provider_id=provider.id
    )
    property_proj = _make_project(
        db_session, seeded_tenant, name="物业自办项目", provider_id=None
    )

    owner = _make_owner(db_session, seeded_tenant)

    case_no_proj = _make_case(db_session, seeded_tenant, owner, project_id=None)
    case_property_proj = _make_case(
        db_session, seeded_tenant, owner, project_id=property_proj.id
    )
    case_provider_proj = _make_case(
        db_session, seeded_tenant, owner, project_id=provider_proj.id
    )

    return SimpleNamespace(
        tenant=seeded_tenant,
        provider=provider,
        provider_proj=provider_proj,
        property_proj=property_proj,
        owner=owner,
        case_no_proj=case_no_proj,
        case_property_proj=case_property_proj,
        case_provider_proj=case_provider_proj,
    )


def _query_case_ids(db_session, scope: SupervisorScope) -> set[int]:
    filt = supervisor_case_filter(scope)
    rows = db_session.execute(
        select(CollectionCase.id).where(filt)
    ).scalars().all()
    return set(rows)


def _query_agent_membership_ids(db_session, scope: SupervisorScope) -> set[int]:
    filt = supervisor_agent_filter(scope)
    rows = db_session.execute(
        select(UserTenantMembership.id).where(filt)
    ).scalars().all()
    return set(rows)


# ---------------------------------------------------------------------------
# supervisor_case_filter 测试
# ---------------------------------------------------------------------------

def test_property_supervisor_sees_no_project_case(db_session, case_env):
    """物业督导必须能看到无项目案件（project_id IS NULL）。"""
    scope = SupervisorScope(tenant_id=case_env.tenant.id, provider_id=None)
    ids = _query_case_ids(db_session, scope)
    assert case_env.case_no_proj.id in ids


def test_property_supervisor_sees_property_project_case(db_session, case_env):
    """物业督导能看到物业自办项目案件（project.provider_id IS NULL）。"""
    scope = SupervisorScope(tenant_id=case_env.tenant.id, provider_id=None)
    ids = _query_case_ids(db_session, scope)
    assert case_env.case_property_proj.id in ids


def test_property_supervisor_cannot_see_provider_project_case(db_session, case_env):
    """物业督导不能看到服务商项目案件。"""
    scope = SupervisorScope(tenant_id=case_env.tenant.id, provider_id=None)
    ids = _query_case_ids(db_session, scope)
    assert case_env.case_provider_proj.id not in ids


def test_provider_supervisor_sees_own_provider_case(db_session, case_env):
    """服务商督导只能看到本服务商项目下的案件。"""
    scope = SupervisorScope(
        tenant_id=case_env.tenant.id, provider_id=case_env.provider.id
    )
    ids = _query_case_ids(db_session, scope)
    assert case_env.case_provider_proj.id in ids


def test_provider_supervisor_cannot_see_no_project_case(db_session, case_env):
    """服务商督导不能看到无项目案件。"""
    scope = SupervisorScope(
        tenant_id=case_env.tenant.id, provider_id=case_env.provider.id
    )
    ids = _query_case_ids(db_session, scope)
    assert case_env.case_no_proj.id not in ids


def test_provider_supervisor_cannot_see_property_project_case(db_session, case_env):
    """服务商督导不能看到物业自办项目案件。"""
    scope = SupervisorScope(
        tenant_id=case_env.tenant.id, provider_id=case_env.provider.id
    )
    ids = _query_case_ids(db_session, scope)
    assert case_env.case_property_proj.id not in ids


def test_provider_supervisor_cannot_see_other_provider_case(db_session, case_env):
    """服务商督导不能看到其他服务商的案件（跨服务商隔离）。"""
    other_prov = _make_provider(db_session, name="另一服务商B", phone="13900000020")
    scope = SupervisorScope(
        tenant_id=case_env.tenant.id, provider_id=other_prov.id
    )
    ids = _query_case_ids(db_session, scope)
    # 该服务商下无项目，故看不到任何案件
    assert case_env.case_provider_proj.id not in ids
    assert case_env.case_property_proj.id not in ids
    assert case_env.case_no_proj.id not in ids


# ---------------------------------------------------------------------------
# supervisor_agent_filter 测试
# ---------------------------------------------------------------------------

@pytest.fixture()
def agent_env(db_session, seeded_tenant):
    provider = _make_provider(db_session, name="外呼服务商C", phone="13900000030")

    mem_property = _make_agent(db_session, seeded_tenant, name="物业催收员", provider_id=None)
    mem_provider = _make_agent(
        db_session, seeded_tenant, name="服务商催收员", provider_id=provider.id
    )
    return SimpleNamespace(
        tenant=seeded_tenant,
        provider=provider,
        mem_property=mem_property,
        mem_provider=mem_provider,
    )


def test_property_supervisor_agent_filter_sees_property_agents(db_session, agent_env):
    """物业督导只看 provider_id IS NULL 的 agent 成员。"""
    scope = SupervisorScope(tenant_id=agent_env.tenant.id, provider_id=None)
    ids = _query_agent_membership_ids(db_session, scope)
    assert agent_env.mem_property.id in ids
    assert agent_env.mem_provider.id not in ids


def test_provider_supervisor_agent_filter_sees_provider_agents(db_session, agent_env):
    """服务商督导只看本服务商 agent 成员。"""
    scope = SupervisorScope(
        tenant_id=agent_env.tenant.id, provider_id=agent_env.provider.id
    )
    ids = _query_agent_membership_ids(db_session, scope)
    assert agent_env.mem_provider.id in ids
    assert agent_env.mem_property.id not in ids


def test_provider_supervisor_agent_filter_cross_provider_isolation(db_session, agent_env):
    """服务商督导看不到其他服务商 agent。"""
    other_prov = _make_provider(db_session, name="第三服务商D", phone="13900000040")
    scope = SupervisorScope(
        tenant_id=agent_env.tenant.id, provider_id=other_prov.id
    )
    ids = _query_agent_membership_ids(db_session, scope)
    assert agent_env.mem_provider.id not in ids
    assert agent_env.mem_property.id not in ids


# ---------------------------------------------------------------------------
# SupervisorScope dataclass 测试
# ---------------------------------------------------------------------------

def test_supervisor_scope_property_side():
    scope = SupervisorScope(tenant_id=1, provider_id=None)
    assert scope.tenant_id == 1
    assert scope.provider_id is None


def test_supervisor_scope_provider_side():
    scope = SupervisorScope(tenant_id=1, provider_id=42)
    assert scope.provider_id == 42


def test_supervisor_scope_is_frozen():
    scope = SupervisorScope(tenant_id=1, provider_id=None)
    with pytest.raises((AttributeError, TypeError)):
        scope.tenant_id = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# supervisor_scope 依赖函数边界测试
# ---------------------------------------------------------------------------

def test_supervisor_scope_rejects_provider_id_zero():
    """payload 中 provider_id=0 属于非法上下文，应抛出 403 ERR_NO_SCOPE。"""
    from fastapi import HTTPException

    payload = {"tenant_id": 1, "provider_id": 0}
    with pytest.raises(HTTPException) as exc_info:
        supervisor_scope(payload)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "ERR_NO_SCOPE"


# ---------------------------------------------------------------------------
# Task 4 — resolve_call_provider_id 测试
# ---------------------------------------------------------------------------

def test_resolve_call_provider_id_no_case(db_session):
    """case_id=None → 返回 None（物业侧）。"""
    result = resolve_call_provider_id(db_session, None)
    assert result is None


def test_resolve_call_provider_id_property_case(db_session, case_env):
    """物业项目案件（project.provider_id=None）→ 返回 None。"""
    result = resolve_call_provider_id(db_session, case_env.case_property_proj.id)
    assert result is None


def test_resolve_call_provider_id_no_project_case(db_session, case_env):
    """无项目案件（project_id=None）→ 返回 None。"""
    result = resolve_call_provider_id(db_session, case_env.case_no_proj.id)
    assert result is None


def test_resolve_call_provider_id_provider_case(db_session, case_env):
    """服务商项目案件 → 返回该服务商 provider_id。"""
    result = resolve_call_provider_id(db_session, case_env.case_provider_proj.id)
    assert result == case_env.provider.id


def test_resolve_call_provider_id_nonexistent_case(db_session, seeded_tenant):
    """不存在的 case_id → 返回 None（无记录时安全降级）。"""
    result = resolve_call_provider_id(db_session, 999999)
    assert result is None
