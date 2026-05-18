"""Task 6 — /supervisor/script-labels scope-aware 三向隔离测试。

场景：
- 服务商 A 督导只见自己服务商项目案件通话的话术反馈
- 服务商 B 督导只见自己服务商项目案件通话的话术反馈
- 物业督导只见物业/无项目案件通话的话术反馈，不见任何服务商案件通话
- POST /supervisor/script-labels/{feedback_id}：跨 scope 的 feedback → 404；本 scope → 200 且字段写入
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
    return f"137{_phone_counter:08d}"


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
        name="业主丙",
        phone_enc=encrypt_phone(_unique_phone()),
        building="3栋",
        room="303",
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
        amount_owed=Decimal("4000.00"),
        priority_score=500,
    )
    db_session.add(case)
    db_session.flush()
    return case


def _make_caller_user(db_session, tenant) -> object:
    """创建一个通话 caller 用户（agent），保证 unique phone。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        name="催收员labels",
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


def _make_script_template(db_session, tenant) -> object:
    """创建一个话术模板，用于 SuggestionFeedback.script_template_id。"""
    from app.models.script import ScriptTemplate

    tmpl = ScriptTemplate(
        tenant_id=tenant.id,
        title="标准开场话术",
        scene="opening",
        trigger_intent="开场",
        content="您好，我是催收专员...",
        version=1,
        is_active=True,
    )
    db_session.add(tmpl)
    db_session.flush()
    return tmpl


def _make_call_with_feedback(
    db_session, tenant, caller, script_template, *, case_id: int | None
) -> tuple[object, object]:
    """创建一条通话 + SuggestionFeedback（script_template_id 非空）。返回 (CallRecord, SuggestionFeedback)。"""
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord, SuggestionFeedback

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

    fb = SuggestionFeedback(
        call_id=call.id,
        suggestion_id=f"sid-{call.id}",
        user_id=caller.id,
        action="adopt",
        script_template_id=script_template.id,
        suggestion_text="建议使用话术模板",
    )
    db_session.add(fb)
    db_session.flush()
    return call, fb


def _make_supervisor_token(db_session, tenant, *, provider_id: int | None) -> str:
    """创建督导用户 + membership，返回 JWT token。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        name="督导labels",
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
def label_scope_env(db_session, seeded_tenant):
    """
    建立以下数据：
    - provider_a / provider_b：服务商 A / B
    - proj_property：物业自办项目（provider_id=None）
    - proj_a / proj_b：服务商 A / B 项目
    - case_property / case_a / case_b：各项目各 1 条案件
    - call_property / call_a / call_b：各案件各 1 条通话
    - fb_property / fb_a / fb_b：各通话各 1 条 SuggestionFeedback（script_template_id 非空）
    - token_property_sv / token_a / token_b：三类督导 token
    """
    provider_a = _make_provider(db_session, name="服务商A-labels")
    provider_b = _make_provider(db_session, name="服务商B-labels")

    proj_property = _make_project(
        db_session, seeded_tenant, name="物业项目-labels", provider_id=None
    )
    proj_a = _make_project(
        db_session, seeded_tenant, name="服务商A项目-labels", provider_id=provider_a.id
    )
    proj_b = _make_project(
        db_session, seeded_tenant, name="服务商B项目-labels", provider_id=provider_b.id
    )

    owner = _make_owner(db_session, seeded_tenant)
    script_tmpl = _make_script_template(db_session, seeded_tenant)

    case_property = _make_case(db_session, seeded_tenant, owner, project_id=proj_property.id)
    case_a = _make_case(db_session, seeded_tenant, owner, project_id=proj_a.id)
    case_b = _make_case(db_session, seeded_tenant, owner, project_id=proj_b.id)

    caller = _make_caller_user(db_session, seeded_tenant)

    call_property, fb_property = _make_call_with_feedback(
        db_session, seeded_tenant, caller, script_tmpl, case_id=case_property.id
    )
    call_a, fb_a = _make_call_with_feedback(
        db_session, seeded_tenant, caller, script_tmpl, case_id=case_a.id
    )
    call_b, fb_b = _make_call_with_feedback(
        db_session, seeded_tenant, caller, script_tmpl, case_id=case_b.id
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
        fb_property=fb_property,
        fb_a=fb_a,
        fb_b=fb_b,
        token_property_sv=token_property_sv,
        token_a=token_a,
        token_b=token_b,
    )


# ---------------------------------------------------------------------------
# 测试 1：GET /supervisor/script-labels 三向隔离
# ---------------------------------------------------------------------------


def test_provider_a_supervisor_sees_only_own_feedback(api, label_scope_env):
    """服务商 A 督导只返回服务商 A 项目案件通话的话术反馈。"""
    resp = api.get(
        "/api/v1/supervisor/script-labels",
        headers=_auth(label_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    ids = {item["feedback_id"] for item in resp.json()}

    assert label_scope_env.fb_a.id in ids
    assert label_scope_env.fb_b.id not in ids
    assert label_scope_env.fb_property.id not in ids


def test_provider_b_supervisor_sees_only_own_feedback(api, label_scope_env):
    """服务商 B 督导只返回服务商 B 项目案件通话的话术反馈。"""
    resp = api.get(
        "/api/v1/supervisor/script-labels",
        headers=_auth(label_scope_env.token_b),
    )
    assert resp.status_code == 200, resp.text
    ids = {item["feedback_id"] for item in resp.json()}

    assert label_scope_env.fb_b.id in ids
    assert label_scope_env.fb_a.id not in ids
    assert label_scope_env.fb_property.id not in ids


def test_property_supervisor_sees_property_feedback_not_provider(api, label_scope_env):
    """物业督导只见物业案件通话的话术反馈，不返回服务商案件通话。"""
    resp = api.get(
        "/api/v1/supervisor/script-labels",
        headers=_auth(label_scope_env.token_property_sv),
    )
    assert resp.status_code == 200, resp.text
    ids = {item["feedback_id"] for item in resp.json()}

    assert label_scope_env.fb_property.id in ids
    assert label_scope_env.fb_a.id not in ids
    assert label_scope_env.fb_b.id not in ids


# ---------------------------------------------------------------------------
# 测试 2：POST /supervisor/script-labels/{feedback_id} 跨 scope 隔离
# ---------------------------------------------------------------------------


def test_label_cross_scope_returns_404(api, label_scope_env):
    """服务商 A 督导标注服务商 B 的 feedback → 404（ERR_NOT_FOUND）。"""
    resp = api.post(
        f"/api/v1/supervisor/script-labels/{label_scope_env.fb_b.id}",
        json={"label": "good"},
        headers=_auth(label_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_label_property_feedback_by_provider_supervisor_returns_404(api, label_scope_env):
    """服务商 A 督导标注物业通话的 feedback → 404（ERR_NOT_FOUND）。"""
    resp = api.post(
        f"/api/v1/supervisor/script-labels/{label_scope_env.fb_property.id}",
        json={"label": "good"},
        headers=_auth(label_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_label_own_feedback_returns_200_and_writes_fields(api, label_scope_env):
    """服务商 A 督导标注自己服务商的 feedback → 200 且 supervisor_label 写入。"""
    resp = api.post(
        f"/api/v1/supervisor/script-labels/{label_scope_env.fb_a.id}",
        json={"label": "good"},
        headers=_auth(label_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["feedback_id"] == label_scope_env.fb_a.id
    assert data["supervisor_label"] == "good"


def test_label_property_supervisor_own_feedback_returns_200(api, label_scope_env):
    """物业督导标注自己物业的 feedback → 200 且 supervisor_label 写入。"""
    resp = api.post(
        f"/api/v1/supervisor/script-labels/{label_scope_env.fb_property.id}",
        json={"label": "bad", "note": "需要改进"},
        headers=_auth(label_scope_env.token_property_sv),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["feedback_id"] == label_scope_env.fb_property.id
    assert data["supervisor_label"] == "bad"
    assert data["supervisor_note"] == "需要改进"
