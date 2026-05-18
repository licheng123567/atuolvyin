"""Task 2 — /supervisor/cases scope-aware 端点三向隔离测试。

场景：
- 服务商 A 督导只返回服务商 A 项目案件
- 服务商 B 督导只返回服务商 B 项目案件
- 物业督导返回无项目案件 + 物业自办项目案件，不返回任何服务商案件
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers: 造数据 & token（与 test_provider_legal.py 风格一致）
# ---------------------------------------------------------------------------

_phone_counter = 0


def _unique_phone() -> str:
    global _phone_counter
    _phone_counter += 1
    return f"139{_phone_counter:08d}"


def _make_provider(db_session, *, name: str) -> object:
    from app.core.crypto import encrypt_phone
    from app.models.tenant import ServiceProvider

    prov = ServiceProvider(
        name=name,
        provider_type="collection",
        admin_phone_enc=encrypt_phone(_unique_phone()),
    )
    db_session.add(prov)
    db_session.flush()
    return prov


def _make_project(db_session, tenant, *, name: str, provider_id: int | None) -> object:
    from app.models.case import Project

    proj = Project(
        tenant_id=tenant.id,
        name=name,
        provider_id=provider_id,
    )
    db_session.add(proj)
    db_session.flush()
    return proj


def _make_owner(db_session, tenant) -> object:
    from app.core.crypto import encrypt_phone
    from app.models.case import OwnerProfile

    owner = OwnerProfile(
        tenant_id=tenant.id,
        name="业主甲",
        phone_enc=encrypt_phone(_unique_phone()),
        building="1栋",
        room="101",
    )
    db_session.add(owner)
    db_session.flush()
    return owner


def _make_case(db_session, tenant, owner, *, project_id: int | None) -> object:
    from app.models.case import CollectionCase

    case = CollectionCase(
        tenant_id=tenant.id,
        project_id=project_id,
        owner_id=owner.id,
        pool_type="public",
        stage="new",
        amount_owed=Decimal("2000.00"),
        priority_score=500,
    )
    db_session.add(case)
    db_session.flush()
    return case


def _make_supervisor_token(db_session, tenant, *, provider_id: int | None) -> str:
    """创建督导用户 + membership，返回 JWT token。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        name="督导用户",
        phone_enc=encrypt_phone(_unique_phone()),
        password_hash=get_password_hash("pw"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    mem = UserTenantMembership(
        tenant_id=tenant.id,
        user_id=user.id,
        role="supervisor",
        provider_id=provider_id,
        is_active=True,
    )
    db_session.add(mem)
    db_session.flush()

    payload: dict = {
        "sub": str(user.id),
        "user_id": user.id,
        "tenant_id": tenant.id,
        "role": "supervisor",
        "scope": f"tenant:{tenant.id}",
    }
    if provider_id is not None:
        payload["provider_id"] = provider_id

    return create_access_token(payload)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixture: 三类项目 + 案件环境
# ---------------------------------------------------------------------------

@pytest.fixture()
def api(db_session):
    from app.core.db import get_db
    from app.main import app

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as cli:
        yield cli
    app.dependency_overrides.clear()


@pytest.fixture()
def scope_env(db_session, seeded_tenant):
    """
    建立以下数据：
    - provider_a: 服务商 A
    - provider_b: 服务商 B
    - proj_property: 物业自办项目（provider_id=None）
    - proj_a: 服务商 A 项目
    - proj_b: 服务商 B 项目
    - case_no_proj: 无项目案件（project_id=None）
    - case_property: 物业项目案件
    - case_a: 服务商 A 项目案件
    - case_b: 服务商 B 项目案件
    - token_property_sv: 物业督导 token
    - token_a: 服务商 A 督导 token
    - token_b: 服务商 B 督导 token
    """
    provider_a = _make_provider(db_session, name="服务商A")
    provider_b = _make_provider(db_session, name="服务商B")

    proj_property = _make_project(
        db_session, seeded_tenant, name="物业自办项目", provider_id=None
    )
    proj_a = _make_project(
        db_session, seeded_tenant, name="服务商A项目", provider_id=provider_a.id
    )
    proj_b = _make_project(
        db_session, seeded_tenant, name="服务商B项目", provider_id=provider_b.id
    )

    owner = _make_owner(db_session, seeded_tenant)

    case_no_proj = _make_case(db_session, seeded_tenant, owner, project_id=None)
    case_property = _make_case(
        db_session, seeded_tenant, owner, project_id=proj_property.id
    )
    case_a = _make_case(db_session, seeded_tenant, owner, project_id=proj_a.id)
    case_b = _make_case(db_session, seeded_tenant, owner, project_id=proj_b.id)

    token_property_sv = _make_supervisor_token(
        db_session, seeded_tenant, provider_id=None
    )
    token_a = _make_supervisor_token(
        db_session, seeded_tenant, provider_id=provider_a.id
    )
    token_b = _make_supervisor_token(
        db_session, seeded_tenant, provider_id=provider_b.id
    )

    return SimpleNamespace(
        tenant=seeded_tenant,
        provider_a=provider_a,
        provider_b=provider_b,
        proj_property=proj_property,
        proj_a=proj_a,
        proj_b=proj_b,
        case_no_proj=case_no_proj,
        case_property=case_property,
        case_a=case_a,
        case_b=case_b,
        token_property_sv=token_property_sv,
        token_a=token_a,
        token_b=token_b,
    )


# ---------------------------------------------------------------------------
# 测试：服务商 A 督导三向隔离
# ---------------------------------------------------------------------------

def test_provider_a_supervisor_sees_only_own_cases(api, scope_env):
    """服务商 A 督导只返回服务商 A 项目的案件，total 正确。"""
    resp = api.get(
        "/api/v1/supervisor/cases",
        headers=_auth(scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    ids = {item["id"] for item in data["items"]}

    # 必须包含自己项目的案件
    assert scope_env.case_a.id in ids
    # 不能包含服务商 B 案件
    assert scope_env.case_b.id not in ids
    # 不能包含物业自办项目案件
    assert scope_env.case_property.id not in ids
    # 不能包含无项目案件
    assert scope_env.case_no_proj.id not in ids
    # total 精确匹配（本 fixture 只建了 1 条 A 案件）
    assert data["total"] == 1


def test_provider_b_supervisor_sees_only_own_cases(api, scope_env):
    """服务商 B 督导只返回服务商 B 项目的案件。"""
    resp = api.get(
        "/api/v1/supervisor/cases",
        headers=_auth(scope_env.token_b),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    ids = {item["id"] for item in data["items"]}

    assert scope_env.case_b.id in ids
    assert scope_env.case_a.id not in ids
    assert scope_env.case_property.id not in ids
    assert scope_env.case_no_proj.id not in ids
    assert data["total"] == 1


# ---------------------------------------------------------------------------
# 测试：物业督导三向隔离
# ---------------------------------------------------------------------------

def test_property_supervisor_sees_property_and_no_project_cases(api, scope_env):
    """物业督导能看到无项目案件 + 物业自办项目案件，不返回任何服务商案件。"""
    resp = api.get(
        "/api/v1/supervisor/cases",
        headers=_auth(scope_env.token_property_sv),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    ids = {item["id"] for item in data["items"]}

    # 物业侧可见
    assert scope_env.case_no_proj.id in ids
    assert scope_env.case_property.id in ids
    # 服务商案件不可见
    assert scope_env.case_a.id not in ids
    assert scope_env.case_b.id not in ids
    # total 精确匹配（无项目 1 条 + 物业项目 1 条）
    assert data["total"] == 2


# ---------------------------------------------------------------------------
# 测试：响应结构完整性（owner 信息）
# ---------------------------------------------------------------------------

def test_provider_a_supervisor_response_has_owner_info(api, scope_env):
    """服务商 A 督导返回的案件条目包含 owner 信息，电话已脱敏。"""
    resp = api.get(
        "/api/v1/supervisor/cases",
        headers=_auth(scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 1
    item = items[0]
    assert "owner" in item
    assert item["owner"]["name"] == "业主甲"
    # 服务商督导：phone 应脱敏（非 11 位明文）
    phone_masked: str = item["owner"]["phone_masked"]
    assert "****" in phone_masked
