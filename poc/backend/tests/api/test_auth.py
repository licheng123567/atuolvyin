import pytest
from httpx import AsyncClient
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.user import UserAccount
from app.models.tenant import Tenant, UserTenantMembership

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


@pytest.fixture
def seeded_user(db_session: Session):
    tenant = Tenant(name="测试物业公司", admin_phone_enc="13900139000", plan="trial")
    db_session.add(tenant)
    db_session.flush()

    user = UserAccount(
        phone_enc="13800138000",
        name="测试管理员",
        password_hash=_pwd.hash("Password123"),
    )
    db_session.add(user)
    db_session.flush()

    membership = UserTenantMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        role="admin",
    )
    db_session.add(membership)
    db_session.commit()
    return user, tenant


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, seeded_user):
    user, tenant = seeded_user
    r = await client.post(
        "/api/v1/auth/login",
        json={"phone": "13800138000", "password": "Password123"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["role"] == "admin"
    assert data["tenant_id"] == tenant.id
    assert data["name"] == "测试管理员"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, seeded_user):
    r = await client.post(
        "/api/v1/auth/login",
        json={"phone": "13800138000", "password": "wrongpassword"},
    )
    assert r.status_code == 401
    assert r.json()["code"] == "ERR_INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_user_not_found(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/login",
        json={"phone": "13700137000", "password": "Password123"},
    )
    assert r.status_code == 401
    assert r.json()["code"] == "ERR_INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_invalid_phone_format(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/login",
        json={"phone": "not-a-phone", "password": "Password123"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, db_session: Session):
    tenant = Tenant(name="另一物业", admin_phone_enc="13600136000", plan="trial")
    db_session.add(tenant)
    db_session.flush()

    user = UserAccount(
        phone_enc="13500135000",
        name="已停用账号",
        password_hash=_pwd.hash("Password123"),
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    r = await client.post(
        "/api/v1/auth/login",
        json={"phone": "13500135000", "password": "Password123"},
    )
    assert r.status_code == 401
