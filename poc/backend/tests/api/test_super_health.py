"""Sprint 15 — System health monitoring tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_services_reports_db_ok(
    client: AsyncClient, super_auth_headers
):
    resp = await client.get(
        "/api/v1/super/health/services", headers=super_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["db"]["status"] in ("ok", "degraded")
    assert isinstance(data["db"]["latency_ms"], int)


@pytest.mark.asyncio
async def test_health_services_returns_full_shape(
    client: AsyncClient, super_auth_headers
):
    resp = await client.get(
        "/api/v1/super/health/services", headers=super_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    for key in ("db", "asr", "llm", "mipush", "websocket"):
        assert key in data
    assert data["asr"]["backend"] == "mock"
    assert data["llm"]["backend"] == "mock"
    assert data["websocket"]["connected_clients"] >= 0


@pytest.mark.asyncio
async def test_health_metrics_returns_shape(
    client: AsyncClient, super_auth_headers
):
    resp = await client.get(
        "/api/v1/super/health/metrics", headers=super_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "asr_p90_sec" in data
    assert "asr_error_rate_24h" in data
    assert "llm_avg_latency_ms" in data
    # No call data seeded → all zero
    assert data["asr_p90_sec"] == 0.0
    assert data["asr_error_rate_24h"] == 0.0


@pytest.mark.asyncio
async def test_health_role_guard(client: AsyncClient, ops_auth_headers):
    resp = await client.get(
        "/api/v1/super/health/services", headers=ops_auth_headers
    )
    assert resp.status_code == 403
