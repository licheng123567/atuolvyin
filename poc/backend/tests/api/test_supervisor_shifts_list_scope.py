"""Phase 2 — GET /supervisor/shifts scope 隔离测试。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_phone_counter = 0


def _unique_phone() -> str:
    global _phone_counter
    _phone_counter += 1
    return f"138{_phone_counter:08d}"


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


def _make_supervisor_user(db_session, tenant, *, provider_id: int | None, username: str) -> object:
    """创建督导用户 + membership，返回 UserAccount。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        name=username,
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
def shifts_env(db_session, seeded_tenant):
    """三类督导 + 两服务商的测试环境。

    - provider_a: 服务商 A
    - provider_b: 服务商 B
    - sup_p: 物业督导（provider_id=None）
    - sup_a: 服务商 A 督导
    - sup_b: 服务商 B 督导
    - token_p / token_a / token_b: 各自 JWT
    """
    provider_a = _make_provider(db_session, name="服务商A_shifts")
    provider_b = _make_provider(db_session, name="服务商B_shifts")

    sup_p = _make_supervisor_user(
        db_session, seeded_tenant, provider_id=None, username="物业督导甲"
    )
    sup_a = _make_supervisor_user(
        db_session, seeded_tenant, provider_id=provider_a.id, username="服务商A督导甲"
    )
    sup_b = _make_supervisor_user(
        db_session, seeded_tenant, provider_id=provider_b.id, username="服务商B督导甲"
    )

    token_p = _make_token(seeded_tenant, sup_p, provider_id=None)
    token_a = _make_token(seeded_tenant, sup_a, provider_id=provider_a.id)
    token_b = _make_token(seeded_tenant, sup_b, provider_id=provider_b.id)

    return SimpleNamespace(
        tenant=seeded_tenant,
        provider_a=provider_a,
        provider_b=provider_b,
        sup_p=sup_p,
        sup_a=sup_a,
        sup_b=sup_b,
        token_p=token_p,
        token_a=token_a,
        token_b=token_b,
    )


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------


def test_provider_a_supervisor_sees_own_empty_week(client, shifts_env):
    """服务商 A 督导首次访问 → 自动播种本服务商一周排班，全空。"""
    resp = client.get(
        "/api/v1/supervisor/shifts", headers=_auth(shifts_env.token_a)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["shifts"]) == 7
    for day in body["shifts"]:
        assert day["morning"] == "" and day["afternoon"] == "" and day["evening"] == ""


def test_dropdown_lists_only_same_scope_supervisors(client, shifts_env):
    """服务商 A 督导的下拉只含服务商 A 的督导，不含 B、不含物业。"""
    resp = client.get(
        "/api/v1/supervisor/shifts", headers=_auth(shifts_env.token_a)
    )
    assert resp.status_code == 200, resp.text
    names = resp.json()["supervisors"]
    assert shifts_env.sup_a.name in names
    assert shifts_env.sup_b.name not in names
    assert shifts_env.sup_p.name not in names


def test_provider_a_seed_does_not_leak_to_property_or_provider_b(
    client, shifts_env, db_session
):
    """服务商 A 督导播种后，物业侧 / 服务商 B 侧排班仍各自独立播种、互不可见。"""
    from app.models.supervisor_shift import SupervisorShift

    client.get("/api/v1/supervisor/shifts", headers=_auth(shifts_env.token_a))
    client.get("/api/v1/supervisor/shifts", headers=_auth(shifts_env.token_p))
    client.get("/api/v1/supervisor/shifts", headers=_auth(shifts_env.token_b))

    rows = db_session.execute(
        sa.select(SupervisorShift).where(
            SupervisorShift.tenant_id == shifts_env.tenant.id
        )
    ).scalars().all()

    by_scope: dict[object, int] = {}
    for r in rows:
        by_scope[r.provider_id] = by_scope.get(r.provider_id, 0) + 1

    # 三个 scope 各 7 天 × 3 slot = 21 行
    assert by_scope.get(None) == 21                        # 物业侧
    assert by_scope.get(shifts_env.provider_a.id) == 21   # 服务商 A
    assert by_scope.get(shifts_env.provider_b.id) == 21   # 服务商 B
