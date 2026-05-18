"""Task 8 — /supervisor/team-performance scope-aware 三向隔离测试。

场景：
- 服务商 A 督导只见服务商 A 的 agent，指标也只聚合 A 的数据
- 服务商 B 督导只见服务商 B 的 agent
- 物业督导只见物业 agent，不含任何服务商 agent
- 指标聚合验证：A 督导看到的 A agent total_calls / promised_cases / paid_cases 精确等于 A 造的数量
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# Unique phone counter — 前缀 139，避开既有测试（Task 5=136, 6=137, 7=138）
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
        name="业主team",
        phone_enc=encrypt_phone(_unique_phone()),
        building="5栋",
        room="505",
    )
    db_session.add(owner)
    db_session.flush()
    return owner


def _make_agent(
    db_session,
    tenant,
    *,
    provider_id: int | None,
    name: str = "催收员team",
) -> object:
    """创建 agent 用户 + 对应 scope 的 membership，返回 UserAccount。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        name=name,
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
        provider_id=provider_id,
        is_active=True,
    )
    db_session.add(mem)
    db_session.flush()
    return user


def _make_case(
    db_session,
    tenant,
    owner,
    *,
    project_id: int | None,
    assigned_to: int,
    stage: str = "new",
) -> object:
    from app.models.case import CollectionCase

    c = CollectionCase(
        tenant_id=tenant.id,
        project_id=project_id,
        owner_id=owner.id,
        pool_type="public",
        stage=stage,
        amount_owed=Decimal("5000.00"),
        priority_score=500,
        assigned_to=assigned_to,
    )
    db_session.add(c)
    db_session.flush()
    return c


def _make_call(
    db_session,
    tenant,
    *,
    caller_user_id: int,
    case_id: int | None,
    billable_duration: int = 0,
    days_ago: int = 1,
) -> object:
    """在近 7 天窗口内造一条通话记录。"""
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=tenant.id,
        caller_user_id=caller_user_id,
        callee_phone_enc=encrypt_phone(_unique_phone()),
        initiated_by="app",
        status="ended",
        recording_mode="post",
        duration_sec=90,
        started_at=datetime.now(UTC) - timedelta(days=days_ago),
        case_id=case_id,
        billable_duration=billable_duration,
    )
    db_session.add(call)
    db_session.flush()
    # 确保 created_at 落在 period_days=7 窗口内
    call.created_at = datetime.now(UTC) - timedelta(days=days_ago)
    db_session.flush()
    return call


def _make_supervisor_token(db_session, tenant, *, provider_id: int | None) -> str:
    """创建督导用户 + membership，返回 JWT token。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        name="督导team",
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
def perf_scope_env(db_session, seeded_tenant):
    """
    建立以下数据：
    - provider_a / provider_b：服务商 A / B
    - proj_property：物业自办项目（provider_id=None）
    - proj_a / proj_b：服务商 A / B 项目
    - agent_property / agent_a / agent_b：各 scope 的催收员（membership.provider_id 对应各 scope）
    - agent_property：2 条 CallRecord（1 connected）+ 3 条 CollectionCase（2 new + 1 promised）
    - agent_a：3 条 CallRecord（2 connected）+ 6 条 CollectionCase（3 new + 2 promised + 1 paid）
    - agent_b：1 条 CallRecord（1 connected）+ 1 条 CollectionCase（1 new）
    - token_property_sv / token_a / token_b：三类督导 token
    """
    provider_a = _make_provider(db_session, name="服务商A-team")
    provider_b = _make_provider(db_session, name="服务商B-team")

    proj_property = _make_project(
        db_session, seeded_tenant, name="物业项目-team", provider_id=None
    )
    proj_a = _make_project(
        db_session, seeded_tenant, name="服务商A项目-team", provider_id=provider_a.id
    )
    proj_b = _make_project(
        db_session, seeded_tenant, name="服务商B项目-team", provider_id=provider_b.id
    )

    owner = _make_owner(db_session, seeded_tenant)

    # 每个 scope 一个 agent
    agent_property = _make_agent(
        db_session, seeded_tenant, provider_id=None, name="物业催收员team"
    )
    agent_a = _make_agent(
        db_session, seeded_tenant, provider_id=provider_a.id, name="服务商A催收员team"
    )
    agent_b = _make_agent(
        db_session, seeded_tenant, provider_id=provider_b.id, name="服务商B催收员team"
    )

    # ── 物业 agent：2 calls (1 connected) + 1 promised case ──
    _make_call(
        db_session, seeded_tenant,
        caller_user_id=agent_property.id,
        case_id=_make_case(
            db_session, seeded_tenant, owner,
            project_id=proj_property.id, assigned_to=agent_property.id
        ).id,
        billable_duration=60,
    )
    _make_call(
        db_session, seeded_tenant,
        caller_user_id=agent_property.id,
        case_id=_make_case(
            db_session, seeded_tenant, owner,
            project_id=proj_property.id, assigned_to=agent_property.id
        ).id,
        billable_duration=0,
    )
    _make_case(
        db_session, seeded_tenant, owner,
        project_id=proj_property.id, assigned_to=agent_property.id, stage="promised"
    )

    # ── 服务商 A agent：3 calls (2 connected) + 2 promised + 1 paid ──
    for i in range(3):
        _make_call(
            db_session, seeded_tenant,
            caller_user_id=agent_a.id,
            case_id=_make_case(
                db_session, seeded_tenant, owner,
                project_id=proj_a.id, assigned_to=agent_a.id
            ).id,
            billable_duration=60 if i < 2 else 0,
        )
    # promised cases for agent_a
    _make_case(
        db_session, seeded_tenant, owner,
        project_id=proj_a.id, assigned_to=agent_a.id, stage="promised"
    )
    _make_case(
        db_session, seeded_tenant, owner,
        project_id=proj_a.id, assigned_to=agent_a.id, stage="promised"
    )
    # paid case for agent_a
    _make_case(
        db_session, seeded_tenant, owner,
        project_id=proj_a.id, assigned_to=agent_a.id, stage="paid"
    )

    # ── 服务商 B agent：1 call + 0 promised ──
    _make_call(
        db_session, seeded_tenant,
        caller_user_id=agent_b.id,
        case_id=_make_case(
            db_session, seeded_tenant, owner,
            project_id=proj_b.id, assigned_to=agent_b.id
        ).id,
        billable_duration=30,
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
        proj_a=proj_a,
        owner=owner,
        agent_property=agent_property,
        agent_a=agent_a,
        agent_b=agent_b,
        token_property_sv=token_property_sv,
        token_a=token_a,
        token_b=token_b,
    )


# ---------------------------------------------------------------------------
# 测试 1：三向隔离断言（user_id 维度）
# ---------------------------------------------------------------------------


def test_provider_a_supervisor_sees_only_provider_a_agent(api, perf_scope_env):
    """服务商 A 督导只返回服务商 A 的 agent，不含物业 agent 和 B agent。"""
    resp = api.get(
        "/api/v1/supervisor/team-performance",
        headers=_auth(perf_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["period_days"] == 7
    user_ids = {item["user_id"] for item in data["items"]}

    assert perf_scope_env.agent_a.id in user_ids
    assert perf_scope_env.agent_b.id not in user_ids
    assert perf_scope_env.agent_property.id not in user_ids


def test_provider_b_supervisor_sees_only_provider_b_agent(api, perf_scope_env):
    """服务商 B 督导只返回服务商 B 的 agent。"""
    resp = api.get(
        "/api/v1/supervisor/team-performance",
        headers=_auth(perf_scope_env.token_b),
    )
    assert resp.status_code == 200, resp.text
    user_ids = {item["user_id"] for item in resp.json()["items"]}

    assert perf_scope_env.agent_b.id in user_ids
    assert perf_scope_env.agent_a.id not in user_ids
    assert perf_scope_env.agent_property.id not in user_ids


def test_property_supervisor_sees_only_property_agent(api, perf_scope_env):
    """物业督导只返回物业 agent，不含服务商 A / B agent。"""
    resp = api.get(
        "/api/v1/supervisor/team-performance",
        headers=_auth(perf_scope_env.token_property_sv),
    )
    assert resp.status_code == 200, resp.text
    user_ids = {item["user_id"] for item in resp.json()["items"]}

    assert perf_scope_env.agent_property.id in user_ids
    assert perf_scope_env.agent_a.id not in user_ids
    assert perf_scope_env.agent_b.id not in user_ids


# ---------------------------------------------------------------------------
# 测试 2：指标聚合也 scoped（服务商 A 督导的 A agent 数据精确）
# ---------------------------------------------------------------------------


def test_provider_a_agent_metrics_match_own_scope_data(api, perf_scope_env):
    """服务商 A 督导看到的 A agent 指标：total_calls=3, connected_calls=2,
    promised_cases=2, paid_cases=1 ——完全来自 A 项目，不串入其他 scope 数据。"""
    resp = api.get(
        "/api/v1/supervisor/team-performance",
        headers=_auth(perf_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    agent_item = next(
        (i for i in items if i["user_id"] == perf_scope_env.agent_a.id), None
    )
    assert agent_item is not None, "服务商 A agent 应出现在结果中"

    assert agent_item["total_calls"] == 3
    assert agent_item["connected_calls"] == 2
    assert agent_item["promised_cases"] == 2
    assert agent_item["paid_cases"] == 1


# ---------------------------------------------------------------------------
# 测试 3：delta×scope — provider scope 下 delta_vs_previous 计算正确
# ---------------------------------------------------------------------------


def test_provider_a_agent_delta_vs_previous_correct(api, perf_scope_env, db_session):
    """服务商 A 督导看到的 A agent delta_vs_previous 精确等于
    (cur_total - prev_total) / prev_total。

    造数据：
    - 当前周期（days_ago=1）：fixture 已造 3 条通话
    - 上一周期（days_ago=10，落在 prev_start=[now-14d, now-7d) 窗口）：额外造 2 条通话
    - 期望 delta = (3 - 2) / 2 = 0.5
    """
    # 上一周期额外为 agent_a 造 2 条通话（days_ago=10 落在 7~14 天前窗口）。
    # supervisor_call_filter 对服务商侧督导要求 case_id IN (proj_a 的案件)，
    # 因此必须为每条通话挂上归属 proj_a 的案件，否则被 scope 过滤掉。
    for _ in range(2):
        case = _make_case(
            db_session,
            perf_scope_env.tenant,
            perf_scope_env.owner,
            project_id=perf_scope_env.proj_a.id,
            assigned_to=perf_scope_env.agent_a.id,
        )
        _make_call(
            db_session,
            perf_scope_env.tenant,
            caller_user_id=perf_scope_env.agent_a.id,
            case_id=case.id,
            billable_duration=60,
            days_ago=10,
        )

    resp = api.get(
        "/api/v1/supervisor/team-performance",
        headers=_auth(perf_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    agent_item = next(
        (i for i in items if i["user_id"] == perf_scope_env.agent_a.id), None
    )
    assert agent_item is not None, "服务商 A agent 应出现在服务商 A 督导的结果中"

    # cur_total=3（fixture 造的当前周期通话），prev_total=2（本测试额外造的上一周期通话）
    # delta = (3 - 2) / 2 = 0.5
    assert agent_item["total_calls"] == 3
    assert agent_item["delta_vs_previous"] == pytest.approx(0.5)
