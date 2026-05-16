"""Sprint 15.1 — 多设备登录踢出 (PRD §11.5).

5 项验收：
  1. login 成功后写 active_session 记录
  2. 同一 user_id + device_type 第二次 login → 旧 token 后续请求 401 ERR_SESSION_EVICTED
  3. PC + App 两种 device_type 可同时在线（互不干扰）
  4. 老 token（active_session 表无记录）仍能访问（向后兼容）
  5. 不同用户互不影响
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


def _seed_user_with_password(db_session, phone: str = "13900000099"):
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.tenant import Tenant, UserTenantMembership
    from app.models.user import UserAccount
    user = UserAccount(
        phone_enc=encrypt_phone(phone),
        name="测试踢出用户",
        password_hash=get_password_hash("Test@1234"),
        is_active=True,
    )
    db_session.add(user); db_session.flush()
    # resolve_identity requires at least one membership; give the user an admin role
    tenant = Tenant(
        name=f"踢出测试租户-{phone}",
        admin_phone_enc=encrypt_phone(phone),
        plan="trial",
        is_active=True,
    )
    db_session.add(tenant)
    db_session.flush()
    membership = UserTenantMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        role="admin",
        is_active=True,
    )
    db_session.add(membership)
    db_session.flush()
    return user


@pytest.mark.asyncio
async def test_login_writes_active_session(client: AsyncClient, db_session):
    user = _seed_user_with_password(db_session)
    db_session.commit()

    r = await client.post(
        "/api/v1/auth/login",
        json={"phone": "13900000099", "password": "Test@1234", "device_type": "pc"},
    )
    assert r.status_code == 200

    from app.models.active_session import ActiveSession
    db_session.expire_all()
    rows = db_session.query(ActiveSession).filter_by(user_id=user.id).all()
    assert len(rows) == 1
    assert rows[0].device_type == "pc"
    assert len(rows[0].token_hash) == 64


@pytest.mark.asyncio
async def test_second_login_same_device_evicts_first(client: AsyncClient, db_session):
    user = _seed_user_with_password(db_session, phone="13900000098")
    db_session.commit()

    # 第一次登录
    r1 = await client.post(
        "/api/v1/auth/login",
        json={"phone": "13900000098", "password": "Test@1234", "device_type": "pc"},
    )
    token1 = r1.json()["access_token"]
    h1 = {"Authorization": f"Bearer {token1}"}

    # token1 现在能用
    me = await client.get("/api/v1/users/me/preferences", headers=h1)
    assert me.status_code == 200

    # 同设备类型第二次登录 → 拿新 token
    r2 = await client.post(
        "/api/v1/auth/login",
        json={"phone": "13900000098", "password": "Test@1234", "device_type": "pc"},
    )
    token2 = r2.json()["access_token"]
    assert token2 != token1

    # 老 token 现在应该被踢
    me_again = await client.get("/api/v1/users/me/preferences", headers=h1)
    assert me_again.status_code == 401
    assert me_again.json()["code"] == "ERR_SESSION_EVICTED"

    # 新 token 还能用
    h2 = {"Authorization": f"Bearer {token2}"}
    me_new = await client.get("/api/v1/users/me/preferences", headers=h2)
    assert me_new.status_code == 200


@pytest.mark.asyncio
async def test_pc_and_app_can_coexist(client: AsyncClient, db_session):
    user = _seed_user_with_password(db_session, phone="13900000097")
    db_session.commit()

    r_pc = await client.post(
        "/api/v1/auth/login",
        json={"phone": "13900000097", "password": "Test@1234", "device_type": "pc"},
    )
    r_app = await client.post(
        "/api/v1/auth/login",
        json={"phone": "13900000097", "password": "Test@1234", "device_type": "app"},
    )
    pc_h = {"Authorization": f"Bearer {r_pc.json()['access_token']}"}
    app_h = {"Authorization": f"Bearer {r_app.json()['access_token']}"}

    # 两个 token 都能用
    assert (await client.get("/api/v1/users/me/preferences", headers=pc_h)).status_code == 200
    assert (await client.get("/api/v1/users/me/preferences", headers=app_h)).status_code == 200


@pytest.mark.asyncio
async def test_legacy_token_without_session_record_still_works(
    client: AsyncClient, ops_auth_headers
):
    # ops_auth_headers 是测试 fixture 直接 create_access_token 出的，没走 login，
    # active_session 无记录 → 应保持向后兼容继续可用
    resp = await client.get("/api/v1/users/me/preferences", headers=ops_auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_eviction_isolated_per_user(client: AsyncClient, db_session):
    u1 = _seed_user_with_password(db_session, phone="13900000091")
    u2 = _seed_user_with_password(db_session, phone="13900000092")
    db_session.commit()

    r1 = await client.post(
        "/api/v1/auth/login",
        json={"phone": "13900000091", "password": "Test@1234", "device_type": "pc"},
    )
    h1 = {"Authorization": f"Bearer {r1.json()['access_token']}"}

    # 另一个用户登录两次，不应影响 u1
    await client.post(
        "/api/v1/auth/login",
        json={"phone": "13900000092", "password": "Test@1234", "device_type": "pc"},
    )
    await client.post(
        "/api/v1/auth/login",
        json={"phone": "13900000092", "password": "Test@1234", "device_type": "pc"},
    )

    me = await client.get("/api/v1/users/me/preferences", headers=h1)
    assert me.status_code == 200, "u1 不该被 u2 的活动踢出"
