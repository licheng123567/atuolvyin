"""Task 5 — /supervisor/reviews scope-aware 三向隔离测试。

场景：
- 服务商 A 督导只返回服务商 A 项目案件通话的质检条目
- 服务商 B 督导只返回服务商 B 项目案件通话的质检条目
- 物业督导返回物业案件通话的质检条目，不返回任何服务商案件通话
- GET  /supervisor/reviews/{call_id}：非本 scope call → 404
- PATCH /supervisor/reviews/{call_id}：非本 scope call → 404；本 scope → 200 且字段写入
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
    return f"136{_phone_counter:08d}"


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
        name="业主乙",
        phone_enc=encrypt_phone(_unique_phone()),
        building="2栋",
        room="202",
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
        amount_owed=Decimal("3000.00"),
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
        name="催收员reviews",
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


def _make_call_with_review(db_session, tenant, caller, *, case_id: int | None) -> object:
    """创建一条通话 + AnalysisResult(needs_review=True)。返回 CallRecord。"""
    from app.core.crypto import encrypt_phone
    from app.models.call import AnalysisResult, CallRecord

    call = CallRecord(
        tenant_id=tenant.id,
        caller_user_id=caller.id,
        callee_phone_enc=encrypt_phone(_unique_phone()),
        initiated_by="app",
        status="ended",
        recording_mode="post",
        duration_sec=120,
        started_at=datetime.now(UTC) - timedelta(hours=1),
        case_id=case_id,
    )
    db_session.add(call)
    db_session.flush()

    analysis = AnalysisResult(
        call_id=call.id,
        needs_review=True,
        summary="AI 摘要",
    )
    db_session.add(analysis)
    db_session.flush()
    return call


def _make_supervisor_token(db_session, tenant, *, provider_id: int | None) -> str:
    """创建督导用户 + membership，返回 JWT token。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        name="督导reviews",
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
def review_scope_env(db_session, seeded_tenant):
    """
    建立以下数据：
    - provider_a / provider_b：服务商 A / B
    - proj_property：物业自办项目（provider_id=None）
    - proj_a / proj_b：服务商 A / B 项目
    - case_property / case_a / case_b：各项目各 1 条案件
    - call_property / call_a / call_b：各案件各 1 条通话（含 AnalysisResult needs_review=True）
    - token_property_sv / token_a / token_b：三类督导 token
    """
    provider_a = _make_provider(db_session, name="服务商A-reviews")
    provider_b = _make_provider(db_session, name="服务商B-reviews")

    proj_property = _make_project(
        db_session, seeded_tenant, name="物业项目-reviews", provider_id=None
    )
    proj_a = _make_project(
        db_session, seeded_tenant, name="服务商A项目-reviews", provider_id=provider_a.id
    )
    proj_b = _make_project(
        db_session, seeded_tenant, name="服务商B项目-reviews", provider_id=provider_b.id
    )

    owner = _make_owner(db_session, seeded_tenant)

    case_property = _make_case(db_session, seeded_tenant, owner, project_id=proj_property.id)
    case_a = _make_case(db_session, seeded_tenant, owner, project_id=proj_a.id)
    case_b = _make_case(db_session, seeded_tenant, owner, project_id=proj_b.id)

    caller_property = _make_caller_user(db_session, seeded_tenant)
    caller_a = _make_caller_user(db_session, seeded_tenant)
    caller_b = _make_caller_user(db_session, seeded_tenant)

    call_property = _make_call_with_review(db_session, seeded_tenant, caller_property, case_id=case_property.id)
    call_a = _make_call_with_review(db_session, seeded_tenant, caller_a, case_id=case_a.id)
    call_b = _make_call_with_review(db_session, seeded_tenant, caller_b, case_id=case_b.id)

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
        token_property_sv=token_property_sv,
        token_a=token_a,
        token_b=token_b,
    )


# ---------------------------------------------------------------------------
# 测试 1：GET /supervisor/reviews 三向隔离
# ---------------------------------------------------------------------------

def test_provider_a_supervisor_sees_only_own_reviews(api, review_scope_env):
    """服务商 A 督导只返回服务商 A 项目案件通话的质检条目。"""
    resp = api.get(
        "/api/v1/supervisor/reviews",
        headers=_auth(review_scope_env.token_a),
        params={"only_pending": "false"},
    )
    assert resp.status_code == 200, resp.text
    ids = {item["call_id"] for item in resp.json()["items"]}

    assert review_scope_env.call_a.id in ids
    assert review_scope_env.call_b.id not in ids
    assert review_scope_env.call_property.id not in ids


def test_provider_b_supervisor_sees_only_own_reviews(api, review_scope_env):
    """服务商 B 督导只返回服务商 B 项目案件通话的质检条目。"""
    resp = api.get(
        "/api/v1/supervisor/reviews",
        headers=_auth(review_scope_env.token_b),
        params={"only_pending": "false"},
    )
    assert resp.status_code == 200, resp.text
    ids = {item["call_id"] for item in resp.json()["items"]}

    assert review_scope_env.call_b.id in ids
    assert review_scope_env.call_a.id not in ids
    assert review_scope_env.call_property.id not in ids


def test_property_supervisor_sees_property_reviews_not_provider(api, review_scope_env):
    """物业督导只看物业案件的通话质检条目，不返回服务商案件通话。"""
    resp = api.get(
        "/api/v1/supervisor/reviews",
        headers=_auth(review_scope_env.token_property_sv),
        params={"only_pending": "false"},
    )
    assert resp.status_code == 200, resp.text
    ids = {item["call_id"] for item in resp.json()["items"]}

    assert review_scope_env.call_property.id in ids
    assert review_scope_env.call_a.id not in ids
    assert review_scope_env.call_b.id not in ids


# ---------------------------------------------------------------------------
# 测试 2：GET /supervisor/reviews/{call_id} 隔离断言
# ---------------------------------------------------------------------------

def test_get_review_detail_cross_scope_returns_404(api, review_scope_env):
    """服务商 A 督导取服务商 B 的 call 详情 → 404。"""
    resp = api.get(
        f"/api/v1/supervisor/reviews/{review_scope_env.call_b.id}",
        headers=_auth(review_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_get_review_detail_property_call_by_provider_supervisor_returns_404(api, review_scope_env):
    """服务商 A 督导取物业 call 详情 → 404。"""
    resp = api.get(
        f"/api/v1/supervisor/reviews/{review_scope_env.call_property.id}",
        headers=_auth(review_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_get_review_detail_own_call_returns_200(api, review_scope_env):
    """服务商 A 督导取自己服务商的 call 详情 → 200。"""
    resp = api.get(
        f"/api/v1/supervisor/reviews/{review_scope_env.call_a.id}",
        headers=_auth(review_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["call_id"] == review_scope_env.call_a.id


# ---------------------------------------------------------------------------
# 测试 3：PATCH /supervisor/reviews/{call_id} 隔离断言
# ---------------------------------------------------------------------------

def test_label_review_cross_scope_returns_404(api, review_scope_env):
    """服务商 A 督导改服务商 B 的 call → 404。"""
    resp = api.patch(
        f"/api/v1/supervisor/reviews/{review_scope_env.call_b.id}",
        json={"quality": "good", "note": "测试"},
        headers=_auth(review_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_label_review_property_call_by_provider_supervisor_returns_404(api, review_scope_env):
    """服务商 A 督导改物业 call → 404。"""
    resp = api.patch(
        f"/api/v1/supervisor/reviews/{review_scope_env.call_property.id}",
        json={"quality": "good", "note": "测试"},
        headers=_auth(review_scope_env.token_a),
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "ERR_NOT_FOUND"


def test_label_review_own_call_returns_200_and_writes_fields(api, review_scope_env):
    """服务商 A 督导改自己服务商的 call → 200，且字段写入。"""
    resp = api.patch(
        f"/api/v1/supervisor/reviews/{review_scope_env.call_a.id}",
        json={"quality": "good", "note": "本服务商通话没问题"},
        headers=_auth(review_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["call_id"] == review_scope_env.call_a.id
    assert data["supervisor_quality"] == "good"
    assert data["supervisor_review_note"] == "本服务商通话没问题"


def test_label_review_property_supervisor_own_call_returns_200(api, review_scope_env):
    """物业督导改自己物业的 call → 200。"""
    resp = api.patch(
        f"/api/v1/supervisor/reviews/{review_scope_env.call_property.id}",
        json={"quality": "bad", "note": "物业侧通话有问题"},
        headers=_auth(review_scope_env.token_property_sv),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["supervisor_quality"] == "bad"
