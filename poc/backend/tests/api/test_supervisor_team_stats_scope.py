"""Task 9 — /supervisor/team-stats scope-aware 三向隔离测试。

场景：
- 服务商 A 督导只见服务商 A 的 agent，指标（漏斗+排名+趋势）只聚合 A 的数据
- 服务商 B 督导只见服务商 B 的 agent
- 物业督导只见物业 agent，不含任何服务商 agent
- funnel / team_ranking 精确值断言：三个 scope 数量不同，能暴露串 scope bug

手机号前缀 150，避开既有测试（Task 5=136, 6=137, 7=138, 8=139）
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# Unique phone counter — 前缀 150
# ---------------------------------------------------------------------------

_phone_counter = 0


def _unique_phone() -> str:
    global _phone_counter
    _phone_counter += 1
    return f"150{_phone_counter:08d}"


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
        name="业主stats",
        phone_enc=encrypt_phone(_unique_phone()),
        building="6栋",
        room="606",
    )
    db_session.add(owner)
    db_session.flush()
    return owner


def _make_agent(
    db_session,
    tenant,
    *,
    provider_id: int | None,
    name: str = "催收员stats",
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
    amount_owed: Decimal = Decimal("1000.00"),
) -> object:
    from app.models.case import CollectionCase

    c = CollectionCase(
        tenant_id=tenant.id,
        project_id=project_id,
        owner_id=owner.id,
        pool_type="public",
        stage=stage,
        amount_owed=amount_owed,
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
    status: str = "ended",
    result_tag: str | None = None,
    days_ago: int = 1,
) -> object:
    """在近 30 天窗口内造一条通话记录（默认 days_ago=1）。"""
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=tenant.id,
        caller_user_id=caller_user_id,
        callee_phone_enc=encrypt_phone(_unique_phone()),
        initiated_by="app",
        status=status,
        recording_mode="post",
        duration_sec=90,
        started_at=datetime.now(UTC) - timedelta(days=days_ago),
        case_id=case_id,
        result_tag=result_tag,
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
        name="督导stats",
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
def stats_scope_env(db_session, seeded_tenant):
    """
    建立以下数据（period_days=30 默认窗口，所有通话 days_ago=1）：

    scope      | outbound | connected | promised | paid cases (amount_owed)
    -----------|----------|-----------|----------|------------------------
    property   |    2     |     1     |    1     | 1 (Decimal('2000.00'))
    provider_A |    4     |     2     |    2     | 2 (Decimal('1500.00') each)
    provider_B |    1     |     0     |    0     | 0

    token_property_sv / token_a / token_b：三类督导 token。
    """
    provider_a = _make_provider(db_session, name="服务商A-stats")
    provider_b = _make_provider(db_session, name="服务商B-stats")

    proj_property = _make_project(
        db_session, seeded_tenant, name="物业项目-stats", provider_id=None
    )
    proj_a = _make_project(
        db_session, seeded_tenant, name="服务商A项目-stats", provider_id=provider_a.id
    )
    proj_b = _make_project(
        db_session, seeded_tenant, name="服务商B项目-stats", provider_id=provider_b.id
    )

    owner = _make_owner(db_session, seeded_tenant)

    # 三个 scope 各一个 agent
    agent_property = _make_agent(
        db_session, seeded_tenant, provider_id=None, name="物业催收员stats"
    )
    agent_a = _make_agent(
        db_session, seeded_tenant, provider_id=provider_a.id, name="服务商A催收员stats"
    )
    agent_b = _make_agent(
        db_session, seeded_tenant, provider_id=provider_b.id, name="服务商B催收员stats"
    )

    # ── 物业 agent：2 outbound（1 completed）+ 1 promised call + 1 paid case ──
    # call 1: completed
    case_p1 = _make_case(
        db_session, seeded_tenant, owner,
        project_id=proj_property.id, assigned_to=agent_property.id,
    )
    _make_call(
        db_session, seeded_tenant,
        caller_user_id=agent_property.id,
        case_id=case_p1.id,
        status="completed",
    )
    # call 2: promised result_tag
    case_p2 = _make_case(
        db_session, seeded_tenant, owner,
        project_id=proj_property.id, assigned_to=agent_property.id,
    )
    _make_call(
        db_session, seeded_tenant,
        caller_user_id=agent_property.id,
        case_id=case_p2.id,
        status="ended",
        result_tag="承诺缴",
    )
    # paid case for property (amount_owed=2000)
    _make_case(
        db_session, seeded_tenant, owner,
        project_id=proj_property.id, assigned_to=agent_property.id,
        stage="paid", amount_owed=Decimal("2000.00"),
    )

    # ── 服务商 A agent：4 outbound（2 completed）+ 2 promised calls + 2 paid cases ──
    # call 1: completed
    case_a1 = _make_case(
        db_session, seeded_tenant, owner,
        project_id=proj_a.id, assigned_to=agent_a.id,
    )
    _make_call(
        db_session, seeded_tenant,
        caller_user_id=agent_a.id,
        case_id=case_a1.id,
        status="completed",
    )
    # call 2: completed
    case_a2 = _make_case(
        db_session, seeded_tenant, owner,
        project_id=proj_a.id, assigned_to=agent_a.id,
    )
    _make_call(
        db_session, seeded_tenant,
        caller_user_id=agent_a.id,
        case_id=case_a2.id,
        status="completed",
    )
    # call 3: promised result_tag
    case_a3 = _make_case(
        db_session, seeded_tenant, owner,
        project_id=proj_a.id, assigned_to=agent_a.id,
    )
    _make_call(
        db_session, seeded_tenant,
        caller_user_id=agent_a.id,
        case_id=case_a3.id,
        status="ended",
        result_tag="承诺缴",
    )
    # call 4: promised result_tag (立即缴)
    case_a4 = _make_case(
        db_session, seeded_tenant, owner,
        project_id=proj_a.id, assigned_to=agent_a.id,
    )
    _make_call(
        db_session, seeded_tenant,
        caller_user_id=agent_a.id,
        case_id=case_a4.id,
        status="ended",
        result_tag="立即缴",
    )
    # 2 paid cases for agent_a (amount_owed=1500 each → total 3000)
    _make_case(
        db_session, seeded_tenant, owner,
        project_id=proj_a.id, assigned_to=agent_a.id,
        stage="paid", amount_owed=Decimal("1500.00"),
    )
    _make_case(
        db_session, seeded_tenant, owner,
        project_id=proj_a.id, assigned_to=agent_a.id,
        stage="paid", amount_owed=Decimal("1500.00"),
    )

    # ── 服务商 B agent：1 outbound（0 completed）+ 0 promised + 0 paid ──
    case_b1 = _make_case(
        db_session, seeded_tenant, owner,
        project_id=proj_b.id, assigned_to=agent_b.id,
    )
    _make_call(
        db_session, seeded_tenant,
        caller_user_id=agent_b.id,
        case_id=case_b1.id,
        status="ended",
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
        agent_property=agent_property,
        agent_a=agent_a,
        agent_b=agent_b,
        token_property_sv=token_property_sv,
        token_a=token_a,
        token_b=token_b,
    )


# ---------------------------------------------------------------------------
# 测试 1：team_ranking 三向隔离（user_id 维度）
# ---------------------------------------------------------------------------


def test_provider_a_supervisor_sees_only_provider_a_agent_in_ranking(
    api, stats_scope_env
):
    """服务商 A 督导的 team_ranking 只含服务商 A agent，不含物业/B agent。"""
    resp = api.get(
        "/api/v1/supervisor/team-stats",
        headers=_auth(stats_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    user_ids = {item["user_id"] for item in data["team_ranking"]}

    assert stats_scope_env.agent_a.id in user_ids
    assert stats_scope_env.agent_b.id not in user_ids
    assert stats_scope_env.agent_property.id not in user_ids


def test_provider_b_supervisor_sees_only_provider_b_agent_in_ranking(
    api, stats_scope_env
):
    """服务商 B 督导的 team_ranking 只含服务商 B agent。"""
    resp = api.get(
        "/api/v1/supervisor/team-stats",
        headers=_auth(stats_scope_env.token_b),
    )
    assert resp.status_code == 200, resp.text
    user_ids = {item["user_id"] for item in resp.json()["team_ranking"]}

    assert stats_scope_env.agent_b.id in user_ids
    assert stats_scope_env.agent_a.id not in user_ids
    assert stats_scope_env.agent_property.id not in user_ids


def test_property_supervisor_sees_only_property_agent_in_ranking(
    api, stats_scope_env
):
    """物业督导的 team_ranking 只含物业 agent，不含服务商 A / B agent。"""
    resp = api.get(
        "/api/v1/supervisor/team-stats",
        headers=_auth(stats_scope_env.token_property_sv),
    )
    assert resp.status_code == 200, resp.text
    user_ids = {item["user_id"] for item in resp.json()["team_ranking"]}

    assert stats_scope_env.agent_property.id in user_ids
    assert stats_scope_env.agent_a.id not in user_ids
    assert stats_scope_env.agent_b.id not in user_ids


# ---------------------------------------------------------------------------
# 测试 2：funnel 精确值断言（三 scope 数量各不同）
# ---------------------------------------------------------------------------


def test_provider_a_funnel_exact_values(api, stats_scope_env):
    """服务商 A 督导 funnel：outbound=4, connected=2, promised=2, paid=2。"""
    resp = api.get(
        "/api/v1/supervisor/team-stats",
        headers=_auth(stats_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    funnel = resp.json()["funnel"]

    assert funnel["outbound"] == 4, f"期望 outbound=4，实际 {funnel['outbound']}"
    assert funnel["connected"] == 2, f"期望 connected=2，实际 {funnel['connected']}"
    assert funnel["promised"] == 2, f"期望 promised=2，实际 {funnel['promised']}"
    assert funnel["paid"] == 2, f"期望 paid=2，实际 {funnel['paid']}"


def test_provider_b_funnel_exact_values(api, stats_scope_env):
    """服务商 B 督导 funnel：outbound=1, connected=0, promised=0, paid=0。"""
    resp = api.get(
        "/api/v1/supervisor/team-stats",
        headers=_auth(stats_scope_env.token_b),
    )
    assert resp.status_code == 200, resp.text
    funnel = resp.json()["funnel"]

    assert funnel["outbound"] == 1, f"期望 outbound=1，实际 {funnel['outbound']}"
    assert funnel["connected"] == 0, f"期望 connected=0，实际 {funnel['connected']}"
    assert funnel["promised"] == 0, f"期望 promised=0，实际 {funnel['promised']}"
    assert funnel["paid"] == 0, f"期望 paid=0，实际 {funnel['paid']}"


def test_property_funnel_exact_values(api, stats_scope_env):
    """物业督导 funnel：outbound=2, connected=1, promised=1, paid=1。"""
    resp = api.get(
        "/api/v1/supervisor/team-stats",
        headers=_auth(stats_scope_env.token_property_sv),
    )
    assert resp.status_code == 200, resp.text
    funnel = resp.json()["funnel"]

    assert funnel["outbound"] == 2, f"期望 outbound=2，实际 {funnel['outbound']}"
    assert funnel["connected"] == 1, f"期望 connected=1，实际 {funnel['connected']}"
    assert funnel["promised"] == 1, f"期望 promised=1，实际 {funnel['promised']}"
    assert funnel["paid"] == 1, f"期望 paid=1，实际 {funnel['paid']}"


# ---------------------------------------------------------------------------
# 测试 3：call_trend 只含本 scope 通话（A scope 有 4 条，B 只有 1 条）
# ---------------------------------------------------------------------------


def test_provider_a_call_trend_counts_only_a_calls(api, stats_scope_env):
    """服务商 A 督导 call_trend 总通话数等于 4（A 的 outbound）。"""
    resp = api.get(
        "/api/v1/supervisor/team-stats",
        headers=_auth(stats_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    call_trend = resp.json()["call_trend"]
    total_outbound = sum(row["outbound"] for row in call_trend)
    assert total_outbound == 4, f"期望 trend 合计 4 条通话，实际 {total_outbound}"


def test_provider_b_call_trend_counts_only_b_calls(api, stats_scope_env):
    """服务商 B 督导 call_trend 总通话数等于 1（B 的 outbound）。"""
    resp = api.get(
        "/api/v1/supervisor/team-stats",
        headers=_auth(stats_scope_env.token_b),
    )
    assert resp.status_code == 200, resp.text
    call_trend = resp.json()["call_trend"]
    total_outbound = sum(row["outbound"] for row in call_trend)
    assert total_outbound == 1, f"期望 trend 合计 1 条通话，实际 {total_outbound}"


# ---------------------------------------------------------------------------
# 测试 4：team_ranking 指标精确值（paid_amount 来自各 scope 案件）
# ---------------------------------------------------------------------------


def test_provider_a_agent_ranking_metrics(api, stats_scope_env):
    """服务商 A 督导 team_ranking A agent：calls=4, connected=2, promises=2,
    paid_amount='3000.00'（2 个 1500 case）。"""
    resp = api.get(
        "/api/v1/supervisor/team-stats",
        headers=_auth(stats_scope_env.token_a),
    )
    assert resp.status_code == 200, resp.text
    ranking = resp.json()["team_ranking"]
    item = next(
        (r for r in ranking if r["user_id"] == stats_scope_env.agent_a.id), None
    )
    assert item is not None, "服务商 A agent 应出现在 team_ranking"
    assert item["calls"] == 4
    assert item["connected"] == 2
    assert item["promises"] == 2
    assert item["paid_amount"] == "3000.00"


def test_property_agent_ranking_metrics(api, stats_scope_env):
    """物业督导 team_ranking 物业 agent：calls=2, connected=1, promises=1,
    paid_amount='2000.00'。"""
    resp = api.get(
        "/api/v1/supervisor/team-stats",
        headers=_auth(stats_scope_env.token_property_sv),
    )
    assert resp.status_code == 200, resp.text
    ranking = resp.json()["team_ranking"]
    item = next(
        (r for r in ranking if r["user_id"] == stats_scope_env.agent_property.id), None
    )
    assert item is not None, "物业 agent 应出现在 team_ranking"
    assert item["calls"] == 2
    assert item["connected"] == 1
    assert item["promises"] == 1
    assert item["paid_amount"] == "2000.00"
