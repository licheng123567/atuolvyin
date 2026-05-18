"""Task 7 — /supervisor/risk-events scope-aware 三向隔离测试。

场景：
- 服务商 A 督导只见服务商 A 项目案件通话的风控事件
- 服务商 B 督导只见服务商 B 项目案件通话的风控事件
- 物业督导只见物业/无项目案件通话的风控事件，不见任何服务商案件通话
- PATCH /supervisor/risk-events/{event_id}：跨 scope 的事件 → 404（ERR_NOT_FOUND）；本 scope → 200 且 disposition_note 写入
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# Unique phone counter (module-level, safe within a single pytest session)
# ---------------------------------------------------------------------------

_phone_counter = 0


def _unique_phone() -> str:
    global _phone_counter
    _phone_counter += 1
    return f"138{_phone_counter:08d}"


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
        name="业主丁",
        phone_enc=encrypt_phone(_unique_phone()),
        building="4栋",
        room="404",
    )
    db_session.add(owner)
    db_session.flush()
    return owner


def _make_case(db_session, tenant, owner, *, project_id: int | None) -> object:
    from app.models.case import CollectionCase

    c = CollectionCase(
        tenant_id=tenant.id,
        project_id=project_id,
        owner_id=owner.id,
        pool_type="public",
        stage="new",
        amount_owed=Decimal("5000.00"),
        priority_score=500,
    )
    db_session.add(c)
    db_session.flush()
    return c


def _make_caller_user(db_session, tenant) -> object:
    """创建一个通话 caller 用户（agent），保证 unique phone。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        name="催收员risk",
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


def _make_call_with_risk_event(
    db_session, tenant, caller, *, case_id: int | None
) -> tuple[object, object]:
    """创建一条通话 + RiskEvent（created_at 在近期窗口内）。返回 (CallRecord, RiskEvent)。"""
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord, RiskEvent

    call = CallRecord(
        tenant_id=tenant.id,
        caller_user_id=caller.id,
        callee_phone_enc=encrypt_phone(_unique_phone()),
        initiated_by="app",
        status="ended",
        recording_mode="post",
        duration_sec=90,
        started_at=datetime.now(UTC) - timedelta(hours=2),
        case_id=case_id,
    )
    db_session.add(call)
    db_session.flush()

    event = RiskEvent(
        call_id=call.id,
        level="L2",
        category="empty_promise",
        intervention="warn",
    )
    db_session.add(event)
    db_session.flush()

    # 确保 created_at 在默认 period_days=7 窗口内
    event.created_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.flush()

    return call, event


def _make_supervisor_token(db_session, tenant, *, provider_id: int | None) -> str:
    """创建督导用户 + membership，返回 JWT token。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        name="督导risk",
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
def risk_scope_env(db_session, seeded_tenant):
    """
    建立以下数据：
    - provider_a / provider_b：服务商 A / B
    - proj_property：物业自办项目（provider_id=None）
    - proj_a / proj_b：服务商 A / B 项目
    - case_property / case_a / case_b：各项目各 1 条案件
    - call_property / call_a / call_b：各案件各 1 条通话
    - event_property / event_a / event_b：各通话各 1 条 RiskEvent（created_at 在 7 天窗口内）
    - token_property_sv / token_a / token_b：三类督导 token
    """
    provider_a = _make_provider(db_session, name="服务商A-risk")
    provider_b = _make_provider(db_session, name="服务商B-risk")

    proj_property = _make_project(
        db_session, seeded_tenant, name="物业项目-risk", provider_id=None
    )
    proj_a = _make_project(
        db_session, seeded_tenant, name="服务商A项目-risk", provider_id=provider_a.id
    )
    proj_b = _make_project(
        db_session, seeded_tenant, name="服务商B项目-risk", provider_id=provider_b.id
    )

    owner = _make_owner(db_session, seeded_tenant)

    case_property = _make_case(db_session, seeded_tenant, owner, project_id=proj_property.id)
    case_a = _make_case(db_session, seeded_tenant, owner, project_id=proj_a.id)
    case_b = _make_case(db_session, seeded_tenant, owner, project_id=proj_b.id)

    caller = _make_caller_user(db_session, seeded_tenant)

    call_property, event_property = _make_call_with_risk_event(
        db_session, seeded_tenant, caller, case_id=case_property.id
    )
    call_a, event_a = _make_call_with_risk_event(
        db_session, seeded_tenant, caller, case_id=case_a.id
    )
    call_b, event_b = _make_call_with_risk_event(
        db_session, seeded_tenant, caller, case_id=case_b.id
    )

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
        call_property=call_property,
        call_a=call_a,
        call_b=call_b,
        event_property=event_property,
        event_a=event_a,
        event_b=event_b,
        token_property_sv=token_property_sv,
        token_a=token_a,
        token_b=token_b,
    )


# ---------------------------------------------------------------------------
# 测试 1：GET /supervisor/risk-events 三向隔离
# ---------------------------------------------------------------------------


def test_provider_a_supervisor_sees_only_own_risk_events(api, risk_scope_env):
    """服务商 A 督导只返回服务商 A 项目案件通话的风控事件。"""
    resp = api.get(
        "/api/v1/supervisor/risk-events",
        headers=_auth(risk_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    ids = {item["id"] for item in resp.json()}

    assert risk_scope_env.event_a.id in ids
    assert risk_scope_env.event_b.id not in ids
    assert risk_scope_env.event_property.id not in ids


def test_provider_b_supervisor_sees_only_own_risk_events(api, risk_scope_env):
    """服务商 B 督导只返回服务商 B 项目案件通话的风控事件。"""
    resp = api.get(
        "/api/v1/supervisor/risk-events",
        headers=_auth(risk_scope_env.token_b),
    )
    assert resp.status_code == 200, resp.text
    ids = {item["id"] for item in resp.json()}

    assert risk_scope_env.event_b.id in ids
    assert risk_scope_env.event_a.id not in ids
    assert risk_scope_env.event_property.id not in ids


def test_property_supervisor_sees_property_risk_events_not_provider(api, risk_scope_env):
    """物业督导只见物业案件通话的风控事件，不返回服务商案件通话。"""
    resp = api.get(
        "/api/v1/supervisor/risk-events",
        headers=_auth(risk_scope_env.token_property_sv),
    )
    assert resp.status_code == 200, resp.text
    ids = {item["id"] for item in resp.json()}

    assert risk_scope_env.event_property.id in ids
    assert risk_scope_env.event_a.id not in ids
    assert risk_scope_env.event_b.id not in ids


# ---------------------------------------------------------------------------
# 测试 2：PATCH /supervisor/risk-events/{event_id} 隔离断言
# ---------------------------------------------------------------------------


def test_annotate_risk_event_cross_scope_returns_404(api, risk_scope_env):
    """服务商 A 督导标注服务商 B 的风控事件 → 404（ERR_NOT_FOUND）。"""
    resp = api.patch(
        f"/api/v1/supervisor/risk-events/{risk_scope_env.event_b.id}",
        json={"note": "跨 scope 标注"},
        headers=_auth(risk_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_annotate_risk_event_property_by_provider_supervisor_returns_404(api, risk_scope_env):
    """服务商 A 督导标注物业通话的风控事件 → 404（ERR_NOT_FOUND）。"""
    resp = api.patch(
        f"/api/v1/supervisor/risk-events/{risk_scope_env.event_property.id}",
        json={"note": "跨 scope 标注"},
        headers=_auth(risk_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_annotate_risk_event_own_returns_200_and_writes_note(api, risk_scope_env):
    """服务商 A 督导标注自己服务商的风控事件 → 200 且 disposition_note 写入。"""
    resp = api.patch(
        f"/api/v1/supervisor/risk-events/{risk_scope_env.event_a.id}",
        json={"note": "已处理，无实质违规"},
        headers=_auth(risk_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == risk_scope_env.event_a.id
    assert data["disposition_note"] == "已处理，无实质违规"


def test_annotate_risk_event_property_supervisor_own_returns_200(api, risk_scope_env):
    """物业督导标注自己物业的风控事件 → 200 且 disposition_note 写入。"""
    resp = api.patch(
        f"/api/v1/supervisor/risk-events/{risk_scope_env.event_property.id}",
        json={"note": "物业侧已核实"},
        headers=_auth(risk_scope_env.token_property_sv),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == risk_scope_env.event_property.id
    assert data["disposition_note"] == "物业侧已核实"
