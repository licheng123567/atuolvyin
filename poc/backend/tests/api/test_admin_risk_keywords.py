import os
import pytest
from httpx import AsyncClient

os.environ.setdefault("RISK_ANALYZER_BACKEND", "mock")


def _platform_super_token():
    from app.core.security import create_access_token
    return create_access_token({"sub": "9999", "user_id": 9999, "tenant_id": 0,
                                "role": "platform_super", "scope": "platform"})


def _tenant_admin_token(tenant_id: int, user_id: int):
    from app.core.security import create_access_token
    return create_access_token({"sub": str(user_id), "user_id": user_id,
                                "tenant_id": tenant_id, "role": "admin",
                                "scope": f"tenant:{tenant_id}"})


@pytest.mark.asyncio
async def test_list_platform_keywords(client, db_session):
    """Platform super can list platform seed keywords."""
    from app.models.risk import RiskKeyword
    kw = RiskKeyword(tenant_id=None, category="owner_threat", speaker="customer", level="L2", keyword="举报")
    db_session.add(kw)
    db_session.flush()

    token = _platform_super_token()
    resp = await client.get("/api/v1/admin/risk-keywords", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(item["keyword"] == "举报" for item in data["items"])


@pytest.mark.asyncio
async def test_create_keyword_as_platform_super(client, db_session):
    token = _platform_super_token()
    payload = {"category": "owner_threat", "speaker": "customer", "level": "L2",
               "keyword": "仲裁", "tenant_id": None}
    resp = await client.post("/api/v1/admin/risk-keywords", json=payload,
                             headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    assert resp.json()["keyword"] == "仲裁"


@pytest.mark.asyncio
async def test_tenant_admin_cannot_modify_platform_keyword(client, db_session, seeded_tenant):
    from app.models.risk import RiskKeyword
    kw = RiskKeyword(tenant_id=None, category="owner_threat", speaker="customer", level="L2", keyword="法院2")
    db_session.add(kw)
    db_session.flush()

    token = _tenant_admin_token(seeded_tenant.id, 1)
    resp = await client.patch(f"/api/v1/admin/risk-keywords/{kw.id}",
                              json={"is_active": False},
                              headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_soft_delete(client, db_session, seeded_tenant):
    from app.models.risk import RiskKeyword
    kw = RiskKeyword(tenant_id=seeded_tenant.id, category="owner_abuse",
                     speaker="customer", level="L1", keyword="混蛋")
    db_session.add(kw)
    db_session.flush()

    token = _tenant_admin_token(seeded_tenant.id, 1)
    resp = await client.delete(f"/api/v1/admin/risk-keywords/{kw.id}",
                               headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    db_session.refresh(kw)
    assert kw.is_active is False


@pytest.mark.asyncio
async def test_wrong_role_gets_403(client, db_session):
    """A non-admin/non-platform_super role cannot access the endpoint."""
    from app.core.security import create_access_token
    token = create_access_token({"sub": "1", "user_id": 1, "tenant_id": 1,
                                 "role": "agent_internal", "scope": "tenant:1"})
    resp = await client.get("/api/v1/admin/risk-keywords",
                            headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_keyword_returns_409(client, db_session, seeded_tenant):
    """Creating the same keyword twice for the same tenant returns 409."""
    token = _tenant_admin_token(seeded_tenant.id, 1)
    payload = {"category": "owner_abuse", "speaker": "customer", "level": "L1", "keyword": "无赖"}
    resp1 = await client.post("/api/v1/admin/risk-keywords", json=payload,
                              headers={"Authorization": f"Bearer {token}"})
    assert resp1.status_code == 201
    resp2 = await client.post("/api/v1/admin/risk-keywords", json=payload,
                              headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 409
