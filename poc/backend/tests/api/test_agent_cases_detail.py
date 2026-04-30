import pytest
from httpx import AsyncClient


@pytest.fixture
def agent_internal_auth_headers(seeded_member_user, seeded_tenant):
    from app.core.security import create_access_token
    token = create_access_token({
        "sub": str(seeded_member_user.id),
        "user_id": seeded_member_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "agent_internal",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def external_agent_user(db_session, seeded_tenant):
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        phone_enc=encrypt_phone("13700007777"),
        name="外包坐席老李",
        password_hash=get_password_hash("External@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserTenantMembership(
        user_id=user.id,
        tenant_id=seeded_tenant.id,
        role="agent_external",
        source_type="EXTERNAL",
        is_active=True,
    ))
    db_session.flush()
    return user


@pytest.fixture
def external_agent_headers(external_agent_user, seeded_tenant):
    from app.core.security import create_access_token
    token = create_access_token({
        "sub": str(external_agent_user.id),
        "user_id": external_agent_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "agent_external",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_agent_internal_gets_plain_phone(
    client: AsyncClient, agent_internal_auth_headers, seeded_case, seeded_owner
):
    resp = await client.get(
        f"/api/v1/agent/cases/{seeded_case.id}", headers=agent_internal_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["owner"]["phone"] == "13712345678"   # decrypted
    assert "****" not in data["owner"]["phone"]


@pytest.mark.asyncio
async def test_agent_external_gets_masked_phone(
    client: AsyncClient, external_agent_headers, seeded_case,
    seeded_owner, db_session, seeded_tenant, external_agent_user
):
    # Assign case to external agent so they can see it
    from app.models.case import CollectionCase
    case = db_session.get(CollectionCase, seeded_case.id)
    case.assigned_to = external_agent_user.id
    case.pool_type = "private"
    db_session.flush()

    resp = await client.get(
        f"/api/v1/agent/cases/{seeded_case.id}", headers=external_agent_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["owner"]["phone"] is None
    assert "****" in data["owner"]["phone_masked"]


@pytest.mark.asyncio
async def test_agent_cannot_see_other_agents_case(
    client: AsyncClient, agent_internal_auth_headers, db_session,
    seeded_tenant, seeded_owner, external_agent_user
):
    from app.models.case import CollectionCase
    # Case assigned to external_agent_user (not seeded_member_user)
    case = CollectionCase(
        tenant_id=seeded_tenant.id,
        owner_id=seeded_owner.id,
        pool_type="private",
        stage="new",
        assigned_to=external_agent_user.id,
        priority_score=0,
    )
    db_session.add(case)
    db_session.flush()

    resp = await client.get(
        f"/api/v1/agent/cases/{case.id}", headers=agent_internal_auth_headers
    )
    assert resp.status_code == 403
