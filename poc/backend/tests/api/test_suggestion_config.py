import pytest


@pytest.mark.asyncio
async def test_get_config_returns_defaults_when_no_record(client, admin_auth_headers):
    resp = await client.get("/api/v1/admin/suggestion-config", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["sensitivity"] == 3
    assert body["max_per_push"] == 3


@pytest.mark.asyncio
async def test_put_config_upserts(client, admin_auth_headers, db_session, seeded_tenant):
    from app.models.script import TenantSuggestionConfig
    from sqlalchemy import select
    resp = await client.put(
        "/api/v1/admin/suggestion-config",
        json={"sensitivity": 5, "max_per_push": 1},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["sensitivity"] == 5

    db_session.expire_all()
    cfg = db_session.execute(
        select(TenantSuggestionConfig).where(TenantSuggestionConfig.tenant_id == seeded_tenant.id)
    ).scalar_one_or_none()
    assert cfg is not None
    assert cfg.sensitivity == 5


@pytest.mark.asyncio
async def test_put_config_validates_range(client, admin_auth_headers):
    resp = await client.put(
        "/api/v1/admin/suggestion-config",
        json={"sensitivity": 6, "max_per_push": 3},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422
