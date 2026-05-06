import pytest


@pytest.mark.asyncio
async def test_dial_request_success(
    client,
    agent_auth_headers,
    seeded_device_with_push_reg,
    seeded_assigned_case,
):
    from app.services import mipush
    mipush._reset_for_tests()

    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": seeded_assigned_case.id},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "dispatched"
    call_id = body["call_id"]
    assert isinstance(call_id, int) and call_id > 0

    sent = mipush._get_mock_sent()
    assert len(sent) == 1
    msg = sent[0]
    assert msg["reg_id"] == "reg-id-xiaomi-abc123"
    assert msg["payload"]["type"] == "DIAL_REQUEST"
    assert msg["payload"]["call_id"] == call_id
    assert msg["payload"]["case_id"] == seeded_assigned_case.id
    assert "owner_name" in msg["payload"]
    assert "owner_phone_masked" in msg["payload"]
    assert "*" in msg["payload"]["owner_phone_masked"]


@pytest.mark.asyncio
async def test_dial_request_case_not_assigned_to_user(
    client,
    agent_auth_headers,
    seeded_device_with_push_reg,
    seeded_case,  # not assigned
):
    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": seeded_case.id},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_FORBIDDEN"


@pytest.mark.asyncio
async def test_dial_request_no_push_reg_id(
    client,
    agent_auth_headers,
    seeded_assigned_case,
    db_session,
    seeded_member_user,
    seeded_tenant,
):
    from app.models.device import DeviceProfile
    device = DeviceProfile(
        device_id="device-no-push",
        user_id=seeded_member_user.id,
        tenant_id=seeded_tenant.id,
        push_reg_id=None,
    )
    db_session.add(device)
    db_session.flush()

    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": seeded_assigned_case.id},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "ERR_PUSH_NOT_REGISTERED"


@pytest.mark.asyncio
async def test_dial_request_uses_stored_push_reg_id(
    client,
    agent_auth_headers,
    seeded_assigned_case,
):
    """End-to-end: register-with-token -> dial-request -> mock receives that token.

    Regression for Sprint 12: before this sprint, /devices/register stripped
    push_reg_id, so DIAL_REQUEST never reached the device. This test goes
    through the public endpoint to prove the full path works.
    """
    from app.services import mipush
    mipush._reset_for_tests()

    reg = await client.post(
        "/api/v1/devices/register",
        json={
            "device_id": "e2e-device-1",
            "brand": "Xiaomi",
            "push_reg_id": "abc123",
            "push_provider": "xiaomi",
        },
        headers=agent_auth_headers,
    )
    assert reg.status_code == 201
    assert reg.json()["push_reg_id_set"] is True

    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": seeded_assigned_case.id},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201, resp.text

    sent = mipush._get_mock_sent()
    assert len(sent) == 1
    assert sent[0]["reg_id"] == "abc123"


@pytest.mark.asyncio
async def test_dial_request_cross_tenant_case(
    client,
    agent_auth_headers,
    seeded_device_with_push_reg,
    db_session,
):
    # Case in a different tenant
    from app.models.tenant import Tenant
    from app.models.case import OwnerProfile, CollectionCase
    from decimal import Decimal
    from app.core.crypto import encrypt_phone

    other_tenant = Tenant(name="别家公司", admin_phone_enc=encrypt_phone("13800000000"), plan="trial", is_active=True)
    db_session.add(other_tenant)
    db_session.flush()
    owner = OwnerProfile(tenant_id=other_tenant.id, name="李四", phone_enc=encrypt_phone("13700000000"))
    db_session.add(owner)
    db_session.flush()
    case = CollectionCase(
        tenant_id=other_tenant.id, owner_id=owner.id,
        pool_type="public", stage="new",
        amount_owed=Decimal("100"), months_overdue=1, priority_score=100,
    )
    db_session.add(case)
    db_session.flush()

    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": case.id},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 404
