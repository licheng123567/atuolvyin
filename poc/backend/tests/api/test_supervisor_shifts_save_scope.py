"""Phase 2 — POST /supervisor/shifts scope 隔离测试。"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from starlette.testclient import TestClient

from app.models.supervisor_shift import SupervisorShift

# ---------------------------------------------------------------------------
# Helpers（同 test_supervisor_shifts_list_scope.py 风格）
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
def shifts_save_env(db_session, seeded_tenant):
    """三类督导（含排班负责人）+ 两服务商的测试环境。

    - provider_a / provider_b: 服务商 A / B
    - sup_p_lead: 物业排班负责人（is_shift_lead=True）
    - sup_a_lead: 服务商 A 排班负责人（is_shift_lead=True）
    - sup_a: 服务商 A 普通督导（is_shift_lead=False）
    - sup_b_lead: 服务商 B 排班负责人（is_shift_lead=True）
    - token_*: 各自 JWT
    """
    provider_a = _make_provider(db_session, name="服务商A_save")
    provider_b = _make_provider(db_session, name="服务商B_save")

    sup_p_lead = _make_supervisor_user(
        db_session, seeded_tenant,
        provider_id=None, username="物业督导_负责人", is_shift_lead=True,
    )
    sup_a_lead = _make_supervisor_user(
        db_session, seeded_tenant,
        provider_id=provider_a.id, username="服务商A督导_负责人", is_shift_lead=True,
    )
    sup_a = _make_supervisor_user(
        db_session, seeded_tenant,
        provider_id=provider_a.id, username="服务商A督导_普通", is_shift_lead=False,
    )
    sup_b_lead = _make_supervisor_user(
        db_session, seeded_tenant,
        provider_id=provider_b.id, username="服务商B督导_负责人", is_shift_lead=True,
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


def test_provider_a_lead_saves_into_own_scope(client, shifts_save_env, db_session):
    """服务商 A 排班负责人保存 → 行落在 provider_id=A，不影响物业/B。"""
    env = shifts_save_env
    today = date.today()
    resp = client.post(
        "/api/v1/supervisor/shifts",
        headers=_auth(env.token_a_lead),
        json={"shifts": [{"date": today.isoformat(), "morning": "服务商A督导",
                          "afternoon": "", "evening": ""}]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["saved"] == 3  # morning + afternoon + evening all processed

    row = db_session.execute(
        sa.select(SupervisorShift)
        .where(SupervisorShift.shift_date == today)
        .where(SupervisorShift.slot == "morning")
        .where(SupervisorShift.provider_id == env.provider_a.id)
    ).scalar_one()
    assert row.supervisor_name == "服务商A督导"

    # 物业侧和服务商B侧不应有任何行（provider_id=None 或 B）
    other_rows = db_session.execute(
        sa.select(SupervisorShift)
        .where(SupervisorShift.shift_date == today)
        .where(SupervisorShift.provider_id != env.provider_a.id)
    ).scalars().all()
    assert len(other_rows) == 0


def test_provider_a_save_does_not_touch_property_rows(
    client, shifts_save_env, db_session
):
    """服务商 A 保存 morning，物业侧同槽位的行不受影响（partial unique 不冲突）。"""
    env = shifts_save_env
    today = date.today()

    # 物业负责人先保存
    resp_p = client.post(
        "/api/v1/supervisor/shifts",
        headers=_auth(env.token_p_lead),
        json={"shifts": [{"date": today.isoformat(), "morning": "物业督导",
                          "afternoon": "", "evening": ""}]},
    )
    assert resp_p.status_code == 200, resp_p.text

    # 服务商 A 负责人再保存
    resp_a = client.post(
        "/api/v1/supervisor/shifts",
        headers=_auth(env.token_a_lead),
        json={"shifts": [{"date": today.isoformat(), "morning": "服务商A督导",
                          "afternoon": "", "evening": ""}]},
    )
    assert resp_a.status_code == 200, resp_a.text

    # 物业侧 morning 应仍是"物业督导"，未被覆盖
    property_row = db_session.execute(
        sa.select(SupervisorShift)
        .where(SupervisorShift.shift_date == today)
        .where(SupervisorShift.slot == "morning")
        .where(SupervisorShift.provider_id.is_(None))
    ).scalar_one()
    assert property_row.supervisor_name == "物业督导"

    # 服务商 A 的 morning 应是"服务商A督导"
    a_row = db_session.execute(
        sa.select(SupervisorShift)
        .where(SupervisorShift.shift_date == today)
        .where(SupervisorShift.slot == "morning")
        .where(SupervisorShift.provider_id == env.provider_a.id)
    ).scalar_one()
    assert a_row.supervisor_name == "服务商A督导"


def test_non_lead_supervisor_still_403(client, shifts_save_env):
    """非排班负责人保存 → 仍 403 ERR_NOT_SHIFT_LEAD（scope 改造不影响该校验）。"""
    env = shifts_save_env
    resp = client.post(
        "/api/v1/supervisor/shifts",
        headers=_auth(env.token_a),
        json={"shifts": []},
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] == "ERR_NOT_SHIFT_LEAD"
