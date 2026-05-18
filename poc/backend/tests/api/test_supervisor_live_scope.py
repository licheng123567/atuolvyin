"""Task 3 — /supervisor/live-calls + force-hangup/takeover scope-aware 三向隔离测试。

场景：
- 服务商 A 督导只返回服务商 A 项目案件的通话，查不到 P0/PB 的
- 服务商 B 督导只返回服务商 B 项目案件的通话
- 物业督导返回物业案件的通话（无 case 或物业 case），不返回任何服务商案件通话
- force-hangup/takeover：非本 scope 的 call → 404（隔离断言）
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# Helper: unique phone counter
# ---------------------------------------------------------------------------

_phone_counter = 0


def _unique_phone() -> str:
    global _phone_counter
    _phone_counter += 1
    return f"139{_phone_counter:08d}"


# ---------------------------------------------------------------------------
# Helpers: 造数据
# ---------------------------------------------------------------------------

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


def _make_caller_user(db_session, tenant) -> object:
    """创建一个通话 caller 用户（agent）。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        name="催收员",
        phone_enc=encrypt_phone(_unique_phone()),
        password_hash=get_password_hash("pw"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    mem = UserTenantMembership(
        tenant_id=tenant.id,
        user_id=user.id,
        role="agent",
        work_mode="internal",
        is_active=True,
    )
    db_session.add(mem)
    db_session.flush()
    return user


def _make_live_call(db_session, tenant, caller, *, case_id: int | None) -> object:
    """创建一条 status='live' 的 CallRecord。"""
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=tenant.id,
        caller_user_id=caller.id,
        callee_phone_enc=encrypt_phone(_unique_phone()),
        initiated_by="app",
        status="live",
        recording_mode="live",
        started_at=datetime.now(UTC) - timedelta(minutes=1),
        last_heartbeat_at=datetime.now(UTC),
        case_id=case_id,
    )
    db_session.add(call)
    db_session.flush()
    return call


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

    token_payload: dict = {
        "sub": str(user.id),
        "user_id": user.id,
        "tenant_id": tenant.id,
        "role": "supervisor",
        "scope": f"tenant:{tenant.id}",
    }
    if provider_id is not None:
        token_payload["provider_id"] = provider_id

    return create_access_token(token_payload)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixture: api client（同步 TestClient）
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


# ---------------------------------------------------------------------------
# Fixture: 三向隔离测试环境
# ---------------------------------------------------------------------------

@pytest.fixture()
def live_scope_env(db_session, seeded_tenant):
    """
    建立以下数据：
    - provider_a / provider_b：服务商 A / B
    - proj_property：物业自办项目（provider_id=None）
    - proj_a / proj_b：服务商 A / B 项目
    - case_property / case_a / case_b：各项目各 1 条案件
    - call_property / call_a / call_b：各案件各 1 条 live 通话
    - call_no_case：无 case_id 的 live 通话（物业督导可见）
    - token_property_sv / token_a / token_b：三类督导 token
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

    case_property = _make_case(db_session, seeded_tenant, owner, project_id=proj_property.id)
    case_a = _make_case(db_session, seeded_tenant, owner, project_id=proj_a.id)
    case_b = _make_case(db_session, seeded_tenant, owner, project_id=proj_b.id)

    # 每条通话需要独立的 caller，因为 uq_active_call_per_caller 约束同一坐席同时只能有一通 live 通话
    caller_property = _make_caller_user(db_session, seeded_tenant)
    caller_a = _make_caller_user(db_session, seeded_tenant)
    caller_b = _make_caller_user(db_session, seeded_tenant)
    caller_no_case = _make_caller_user(db_session, seeded_tenant)

    call_property = _make_live_call(db_session, seeded_tenant, caller_property, case_id=case_property.id)
    call_a = _make_live_call(db_session, seeded_tenant, caller_a, case_id=case_a.id)
    call_b = _make_live_call(db_session, seeded_tenant, caller_b, case_id=case_b.id)
    # 无 case 的通话：物业督导可见，服务商督导不可见
    call_no_case = _make_live_call(db_session, seeded_tenant, caller_no_case, case_id=None)

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
        case_property=case_property,
        case_a=case_a,
        case_b=case_b,
        call_property=call_property,
        call_a=call_a,
        call_b=call_b,
        call_no_case=call_no_case,
        token_property_sv=token_property_sv,
        token_a=token_a,
        token_b=token_b,
    )


# ---------------------------------------------------------------------------
# 测试 1：GET /supervisor/live-calls 三向隔离
# ---------------------------------------------------------------------------

def test_provider_a_supervisor_sees_only_own_calls(api, live_scope_env):
    """服务商 A 督导只返回服务商 A 项目案件的通话。"""
    resp = api.get(
        "/api/v1/supervisor/live-calls",
        headers=_auth(live_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    ids = {item["call_id"] for item in resp.json()["items"]}

    # 必须包含自己服务商的通话
    assert live_scope_env.call_a.id in ids
    # 不能包含服务商 B 的通话
    assert live_scope_env.call_b.id not in ids
    # 不能包含物业项目的通话
    assert live_scope_env.call_property.id not in ids
    # 不能包含无 case 的通话（服务商督导不可见）
    assert live_scope_env.call_no_case.id not in ids


def test_provider_b_supervisor_sees_only_own_calls(api, live_scope_env):
    """服务商 B 督导只返回服务商 B 项目案件的通话。"""
    resp = api.get(
        "/api/v1/supervisor/live-calls",
        headers=_auth(live_scope_env.token_b),
    )
    assert resp.status_code == 200, resp.text
    ids = {item["call_id"] for item in resp.json()["items"]}

    assert live_scope_env.call_b.id in ids
    assert live_scope_env.call_a.id not in ids
    assert live_scope_env.call_property.id not in ids
    assert live_scope_env.call_no_case.id not in ids


def test_property_supervisor_sees_property_calls_not_provider_calls(api, live_scope_env):
    """物业督导返回物业项目通话 + 无 case 通话，不返回任何服务商通话。"""
    resp = api.get(
        "/api/v1/supervisor/live-calls",
        headers=_auth(live_scope_env.token_property_sv),
    )
    assert resp.status_code == 200, resp.text
    ids = {item["call_id"] for item in resp.json()["items"]}

    # 物业侧可见
    assert live_scope_env.call_property.id in ids
    assert live_scope_env.call_no_case.id in ids
    # 服务商通话不可见
    assert live_scope_env.call_a.id not in ids
    assert live_scope_env.call_b.id not in ids


# ---------------------------------------------------------------------------
# 测试 2：POST /supervisor/calls/{id}/force-hangup 隔离断言
# ---------------------------------------------------------------------------

def test_force_hangup_cross_scope_returns_404(api, live_scope_env):
    """服务商 A 督导对服务商 B 的通话 force-hangup → 404。"""
    resp = api.post(
        f"/api/v1/supervisor/calls/{live_scope_env.call_b.id}/force-hangup",
        json={"reason": "测试隔离"},
        headers=_auth(live_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_force_hangup_property_call_by_provider_supervisor_returns_404(api, live_scope_env):
    """服务商 A 督导对物业项目通话 force-hangup → 404。"""
    resp = api.post(
        f"/api/v1/supervisor/calls/{live_scope_env.call_property.id}/force-hangup",
        json={"reason": "测试隔离"},
        headers=_auth(live_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_force_hangup_no_case_call_by_provider_supervisor_returns_404(api, live_scope_env):
    """服务商 A 督导对无 case 通话 force-hangup → 404（无归属，服务商不可见）。"""
    resp = api.post(
        f"/api/v1/supervisor/calls/{live_scope_env.call_no_case.id}/force-hangup",
        json={"reason": "测试隔离"},
        headers=_auth(live_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_force_hangup_provider_call_by_property_supervisor_returns_404(api, live_scope_env):
    """物业督导对服务商 A 通话 force-hangup → 404。"""
    resp = api.post(
        f"/api/v1/supervisor/calls/{live_scope_env.call_a.id}/force-hangup",
        json={"reason": "测试隔离"},
        headers=_auth(live_scope_env.token_property_sv),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


# ---------------------------------------------------------------------------
# 测试 3：POST /supervisor/calls/{id}/takeover 隔离断言
# ---------------------------------------------------------------------------

def test_takeover_cross_scope_returns_404(api, live_scope_env):
    """服务商 A 督导对服务商 B 的通话 takeover → 404。"""
    resp = api.post(
        f"/api/v1/supervisor/calls/{live_scope_env.call_b.id}/takeover",
        json={"reason": "测试隔离"},
        headers=_auth(live_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_takeover_property_call_by_provider_supervisor_returns_404(api, live_scope_env):
    """服务商 A 督导对物业项目通话 takeover → 404。"""
    resp = api.post(
        f"/api/v1/supervisor/calls/{live_scope_env.call_property.id}/takeover",
        json={"reason": "测试隔离"},
        headers=_auth(live_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_takeover_no_case_call_by_provider_supervisor_returns_404(api, live_scope_env):
    """服务商 A 督导对无 case 通话 takeover → 404。"""
    resp = api.post(
        f"/api/v1/supervisor/calls/{live_scope_env.call_no_case.id}/takeover",
        json={"reason": "测试隔离"},
        headers=_auth(live_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_takeover_provider_call_by_property_supervisor_returns_404(api, live_scope_env):
    """物业督导对服务商 A 通话 takeover → 404。"""
    resp = api.post(
        f"/api/v1/supervisor/calls/{live_scope_env.call_a.id}/takeover",
        json={"reason": "测试隔离"},
        headers=_auth(live_scope_env.token_property_sv),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"
