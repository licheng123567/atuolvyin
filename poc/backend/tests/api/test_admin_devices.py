"""Sprint 12 — admin /devices troubleshooting endpoint tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_devices_returns_tenant_devices(
    client: AsyncClient,
    seeded_device_with_push_reg,
    admin_auth_headers,
):
    resp = await client.get("/api/v1/admin/devices", headers=admin_auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert any(d["device_id"] == "test-device-001" for d in items)
    found = next(d for d in items if d["device_id"] == "test-device-001")
    # raw push_reg_id must NEVER be exposed
    assert "push_reg_id" not in found
    assert found["push_reg_id_set"] is True
    assert found["push_provider"] == "xiaomi"


@pytest.mark.asyncio
async def test_list_devices_filter_by_user_id(
    client: AsyncClient,
    seeded_device_with_push_reg,
    seeded_member_user,
    admin_auth_headers,
    db_session,
    seeded_tenant,
):
    """Filtering by user_id returns only that user's devices."""
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.device import DeviceProfile
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    # Seed a second user in the same tenant with their own device
    other = UserAccount(
        phone_enc=encrypt_phone("13700137001"),
        name="另一个催收员",
        password_hash=get_password_hash("Other@1234"),
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=other.id,
            tenant_id=seeded_tenant.id,
            role="agent",
            work_mode="internal",
            is_active=True,
        )
    )
    db_session.add(
        DeviceProfile(
            device_id="other-device",
            user_id=other.id,
            tenant_id=seeded_tenant.id,
            push_reg_id="other-token",
            push_provider="huawei",
        )
    )
    db_session.flush()

    # Filter by the original member user's id
    resp = await client.get(
        f"/api/v1/admin/devices?user_id={seeded_member_user.id}",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()
    assert all(d["user_id"] == seeded_member_user.id for d in items)
    assert any(d["device_id"] == "test-device-001" for d in items)
    assert not any(d["device_id"] == "other-device" for d in items)


@pytest.mark.asyncio
async def test_list_devices_cross_tenant_invisible(
    client: AsyncClient,
    admin_auth_headers,
    db_session,
):
    """Devices in other tenants must not appear."""
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.device import DeviceProfile
    from app.models.tenant import Tenant, UserTenantMembership
    from app.models.user import UserAccount

    other_tenant = Tenant(
        name="别家公司",
        admin_phone_enc=encrypt_phone("13800000000"),
        plan="trial",
        is_active=True,
    )
    db_session.add(other_tenant)
    db_session.flush()
    other_user = UserAccount(
        phone_enc=encrypt_phone("13600136000"),
        name="他司员工",
        password_hash=get_password_hash("Other@1234"),
        is_active=True,
    )
    db_session.add(other_user)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=other_user.id,
            tenant_id=other_tenant.id,
            role="agent",
            work_mode="internal",
            is_active=True,
        )
    )
    db_session.add(
        DeviceProfile(
            device_id="cross-tenant-device",
            user_id=other_user.id,
            tenant_id=other_tenant.id,
            push_reg_id="cross-token",
            push_provider="xiaomi",
        )
    )
    db_session.flush()

    resp = await client.get("/api/v1/admin/devices", headers=admin_auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert not any(d["device_id"] == "cross-tenant-device" for d in items)


@pytest.mark.asyncio
async def test_list_devices_requires_admin_role(
    client: AsyncClient, agent_auth_headers
):
    resp = await client.get("/api/v1/admin/devices", headers=agent_auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_devices_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/admin/devices")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_devices_push_reg_id_set_false_when_null(
    client: AsyncClient,
    admin_auth_headers,
    db_session,
    seeded_member_user,
    seeded_tenant,
):
    """A device with no push token shows push_reg_id_set=False."""
    from app.models.device import DeviceProfile

    db_session.add(
        DeviceProfile(
            device_id="no-token-device",
            user_id=seeded_member_user.id,
            tenant_id=seeded_tenant.id,
            push_reg_id=None,
            push_provider=None,
        )
    )
    db_session.flush()

    resp = await client.get("/api/v1/admin/devices", headers=admin_auth_headers)
    assert resp.status_code == 200
    found = next(d for d in resp.json() if d["device_id"] == "no-token-device")
    assert found["push_reg_id_set"] is False
    assert found["push_provider"] is None
