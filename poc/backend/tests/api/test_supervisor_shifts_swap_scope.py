"""Phase 2 — swap-request / swap-requests scope 隔离测试。"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers（同 test_supervisor_shifts_list_scope.py / save_scope.py 风格）
# ---------------------------------------------------------------------------

_phone_counter = 0


def _unique_phone() -> str:
    global _phone_counter
    _phone_counter += 1
    return f"137{_phone_counter:08d}"


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


def _make_supervisor_user(
    db_session,
    tenant,
    *,
    provider_id: int | None,
    username: str,
    is_shift_lead: bool = False,
) -> object:
    """创建督导用户 + membership，返回 UserAccount。is_shift_lead=True 时设 preferences。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        name=username,
        phone_enc=encrypt_phone(_unique_phone()),
        password_hash=get_password_hash("pw"),
        is_active=True,
        preferences={"is_shift_lead": True} if is_shift_lead else {},
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
    return user


def _make_token(tenant, user, *, provider_id: int | None) -> str:
    from app.core.security import create_access_token

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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(db_session):
    from app.core.db import get_db
    from app.main import app

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as cli:
        yield cli
    app.dependency_overrides.clear()


@pytest.fixture()
def shifts_swap_env(db_session, seeded_tenant):
    """三类督导（含排班负责人）+ 两服务商的测试环境。

    - provider_a / provider_b: 服务商 A / B
    - sup_p_lead: 物业排班负责人（is_shift_lead=True）
    - sup_a_lead: 服务商 A 排班负责人（is_shift_lead=True）
    - sup_a: 服务商 A 普通督导（is_shift_lead=False，也是 swap 发起者）
    - sup_b_lead: 服务商 B 排班负责人（is_shift_lead=True）
    - token_*: 各自 JWT
    """
    provider_a = _make_provider(db_session, name="服务商A_swap")
    provider_b = _make_provider(db_session, name="服务商B_swap")

    sup_p_lead = _make_supervisor_user(
        db_session, seeded_tenant,
        provider_id=None, username="物业督导_swap_负责人", is_shift_lead=True,
    )
    sup_a_lead = _make_supervisor_user(
        db_session, seeded_tenant,
        provider_id=provider_a.id, username="服务商A督导_swap_负责人", is_shift_lead=True,
    )
    sup_a = _make_supervisor_user(
        db_session, seeded_tenant,
        provider_id=provider_a.id, username="服务商A督导_swap_甲", is_shift_lead=False,
    )
    sup_b_lead = _make_supervisor_user(
        db_session, seeded_tenant,
        provider_id=provider_b.id, username="服务商B督导_swap_负责人", is_shift_lead=True,
    )

    token_p_lead = _make_token(seeded_tenant, sup_p_lead, provider_id=None)
    token_a_lead = _make_token(seeded_tenant, sup_a_lead, provider_id=provider_a.id)
    token_a = _make_token(seeded_tenant, sup_a, provider_id=provider_a.id)
    token_b_lead = _make_token(seeded_tenant, sup_b_lead, provider_id=provider_b.id)

    return SimpleNamespace(
        tenant=seeded_tenant,
        provider_a=provider_a,
        provider_b=provider_b,
        sup_p_lead=sup_p_lead,
        sup_a_lead=sup_a_lead,
        sup_a=sup_a,
        sup_b_lead=sup_b_lead,
        token_p_lead=token_p_lead,
        token_a_lead=token_a_lead,
        token_a=token_a,
        token_b_lead=token_b_lead,
    )


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------


def _seed_own_slot(client, lead_token: str, slot_owner_name: str) -> date:
    """用排班负责人把今天 morning 排给某督导，返回该日期。"""
    today = date.today()
    client.post(
        "/api/v1/supervisor/shifts",
        headers=_auth(lead_token),
        json={"shifts": [{"date": today.isoformat(), "morning": slot_owner_name,
                          "afternoon": "", "evening": ""}]},
    )
    return today


def test_provider_a_swap_request_scoped(client, shifts_swap_env, db_session):
    """服务商 A 督导对自己班次发起调班 → swap request 带 provider_id=A。"""
    from app.models.supervisor_shift import SupervisorShiftSwapRequest

    env = shifts_swap_env
    # 让 A lead 把今天 morning 排给 sup_a_lead 自己（因为 is_shift_lead 用的是 a_lead）
    today = _seed_own_slot(client, env.token_a_lead, env.sup_a_lead.name)

    resp = client.post(
        "/api/v1/supervisor/shifts/swap-request",
        headers=_auth(env.token_a_lead),
        json={"date": today.isoformat(), "slot": "morning", "swap_with": "另一个督导"},
    )
    assert resp.status_code == 200, resp.text
    req = db_session.get(SupervisorShiftSwapRequest, resp.json()["id"])
    assert req.provider_id == env.provider_a.id


def test_swap_requests_list_isolated(client, shifts_swap_env, db_session):
    """服务商 A 的调班申请，服务商 B 督导与物业督导都查不到。"""
    env = shifts_swap_env
    # 服务商 A lead 把今天 morning 排给自己，然后发起调班
    today = _seed_own_slot(client, env.token_a_lead, env.sup_a_lead.name)
    resp = client.post(
        "/api/v1/supervisor/shifts/swap-request",
        headers=_auth(env.token_a_lead),
        json={"date": today.isoformat(), "slot": "morning", "swap_with": "X"},
    )
    assert resp.status_code == 200, resp.text

    a_list = client.get(
        "/api/v1/supervisor/shifts/swap-requests", headers=_auth(env.token_a_lead)
    ).json()
    b_list = client.get(
        "/api/v1/supervisor/shifts/swap-requests", headers=_auth(env.token_b_lead)
    ).json()
    p_list = client.get(
        "/api/v1/supervisor/shifts/swap-requests", headers=_auth(env.token_p_lead)
    ).json()

    assert len(a_list) == 1
    assert b_list == []
    assert p_list == []


def test_swap_request_own_slot_check_scoped(client, shifts_swap_env):
    """物业侧把 morning 排给与服务商A督导同名的人，服务商A督导仍只能对"本scope自己的班次"发起。

    校验 _shift_scope_clause 让"自有班次"判断不跨 scope 命中。
    """
    env = shifts_swap_env
    today = date.today()

    # 物业侧把 morning 排给 sup_a_lead.name（同名）
    client.post(
        "/api/v1/supervisor/shifts",
        headers=_auth(env.token_p_lead),
        json={"shifts": [{"date": today.isoformat(), "morning": env.sup_a_lead.name,
                          "afternoon": "", "evening": ""}]},
    )
    # 服务商A scope 下 morning 仍是空（没排给 sup_a_lead）→ 发起调班应 403 ERR_NOT_OWN_SLOT
    resp = client.post(
        "/api/v1/supervisor/shifts/swap-request",
        headers=_auth(env.token_a_lead),
        json={"date": today.isoformat(), "slot": "morning", "swap_with": "X"},
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "ERR_NOT_OWN_SLOT"


def test_non_lead_can_submit_swap_request(client, shifts_swap_env):
    """普通督导（is_shift_lead=False）可对自己的班次发起调班 — swap 端点不要求 is_shift_lead。

    与 save_shifts 形成对比：save_shifts 要求 is_shift_lead，swap-request 不要求。
    流程：
    1. 用 token_a_lead（排班负责人）把今天 morning 排给 sup_a（普通督导）。
    2. 用 token_a（普通督导，is_shift_lead=False）对该班次发起 swap-request。
    3. 断言 200 成功，证明鉴权不依赖 is_shift_lead。
    """
    env = shifts_swap_env
    # 步骤 1：负责人把今天 morning 排给普通督导 sup_a
    today = _seed_own_slot(client, env.token_a_lead, env.sup_a.name)

    # 步骤 2：普通督导（非 lead）用自己的 token 发起调班
    resp = client.post(
        "/api/v1/supervisor/shifts/swap-request",
        headers=_auth(env.token_a),
        json={"date": today.isoformat(), "slot": "morning", "swap_with": "服务商A督导_swap_负责人"},
    )
    # 步骤 3：断言 200 — 无需 is_shift_lead
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["from_user"] == env.sup_a.name
    assert data["status"] == "pending_confirm"
