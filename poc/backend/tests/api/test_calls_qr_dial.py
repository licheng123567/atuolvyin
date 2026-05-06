"""Sprint 12 — QR dial backup flow tests.

dial-request mode=qr returns a deeplink + token.
GET /calls/{id}/dial-info?token=… consumes it once and returns case info.

These cover: happy path, replay protection, expiration, wrong call_id,
push mode still works, and validation.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


@pytest.fixture
def assigned_case_for_agent(db_session, seeded_tenant, seeded_member_user, seeded_owner):
    from decimal import Decimal

    from app.models.case import CollectionCase

    case = CollectionCase(
        tenant_id=seeded_tenant.id,
        owner_id=seeded_owner.id,
        pool_type="private",
        stage="contacted",
        amount_owed=Decimal("4500.00"),
        months_overdue=2,
        priority_score=900,
        assigned_to=seeded_member_user.id,
    )
    db_session.add(case)
    db_session.flush()
    return case


# ── dial-request mode=qr ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dial_request_qr_returns_payload_and_token(
    client: AsyncClient,
    assigned_case_for_agent,
    agent_auth_headers,
):
    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": assigned_case_for_agent.id, "mode": "qr"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "qr_pending"
    assert data["call_id"] > 0
    assert data["qr_payload"].startswith("autoluyin://dial?call_id=")
    assert "&token=" in data["qr_payload"]
    assert data["expires_at"] is not None


@pytest.mark.asyncio
async def test_dial_request_qr_does_not_require_push_device(
    client: AsyncClient,
    assigned_case_for_agent,
    agent_auth_headers,
):
    """Even without any registered device, qr mode succeeds."""
    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": assigned_case_for_agent.id, "mode": "qr"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_dial_request_invalid_mode_422(
    client: AsyncClient, assigned_case_for_agent, agent_auth_headers
):
    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": assigned_case_for_agent.id, "mode": "weird"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_dial_request_qr_unassigned_case_403(
    client: AsyncClient, seeded_case, agent_auth_headers
):
    """seeded_case has no assigned_to — must be rejected even for qr mode."""
    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": seeded_case.id, "mode": "qr"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 403


# ── dial-info ────────────────────────────────────────────────────────


def _extract_token(qr_payload: str) -> str:
    return qr_payload.split("&token=")[-1]


@pytest.mark.asyncio
async def test_dial_info_returns_case_payload(
    client: AsyncClient,
    assigned_case_for_agent,
    seeded_owner,
    agent_auth_headers,
):
    req = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": assigned_case_for_agent.id, "mode": "qr"},
        headers=agent_auth_headers,
    )
    payload = req.json()
    token = _extract_token(payload["qr_payload"])
    call_id = payload["call_id"]

    resp = await client.get(
        f"/api/v1/calls/{call_id}/dial-info", params={"token": token}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["call_id"] == call_id
    assert data["case_id"] == assigned_case_for_agent.id
    assert data["owner_name"] == seeded_owner.name
    assert "****" in data["owner_phone_masked"]
    assert data["owner_phone_enc"]  # ciphertext present for App-side decrypt
    assert data["debt_amount"] == 4500.0
    assert data["months_overdue"] == 2


@pytest.mark.asyncio
async def test_dial_info_token_is_one_shot(
    client: AsyncClient,
    assigned_case_for_agent,
    agent_auth_headers,
):
    req = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": assigned_case_for_agent.id, "mode": "qr"},
        headers=agent_auth_headers,
    )
    token = _extract_token(req.json()["qr_payload"])
    call_id = req.json()["call_id"]

    first = await client.get(
        f"/api/v1/calls/{call_id}/dial-info", params={"token": token}
    )
    assert first.status_code == 200

    second = await client.get(
        f"/api/v1/calls/{call_id}/dial-info", params={"token": token}
    )
    assert second.status_code == 401
    assert second.json()["code"] == "ERR_INVALID_DIAL_TOKEN"


@pytest.mark.asyncio
async def test_dial_info_token_expires(
    client: AsyncClient,
    db_session,
    assigned_case_for_agent,
    agent_auth_headers,
):
    from app.models.dial_token import DialToken

    req = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": assigned_case_for_agent.id, "mode": "qr"},
        headers=agent_auth_headers,
    )
    token = _extract_token(req.json()["qr_payload"])
    call_id = req.json()["call_id"]

    # Forcibly age the token
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    dt = db_session.execute(
        DialToken.__table__.select().where(DialToken.token_hash == token_hash)
    ).first()
    assert dt is not None
    db_session.execute(
        DialToken.__table__.update()
        .where(DialToken.token_hash == token_hash)
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    db_session.commit()

    resp = await client.get(
        f"/api/v1/calls/{call_id}/dial-info", params={"token": token}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dial_info_wrong_call_id_rejected(
    client: AsyncClient,
    assigned_case_for_agent,
    agent_auth_headers,
):
    req = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": assigned_case_for_agent.id, "mode": "qr"},
        headers=agent_auth_headers,
    )
    token = _extract_token(req.json()["qr_payload"])

    resp = await client.get(
        "/api/v1/calls/999999/dial-info", params={"token": token}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_dial_info_unknown_token_401(client: AsyncClient):
    resp = await client.get(
        "/api/v1/calls/1/dial-info", params={"token": "not-a-valid-token-xxx"}
    )
    assert resp.status_code == 401


# ── push mode regression — must still work ───────────────────────────


@pytest.mark.asyncio
async def test_dial_request_push_mode_default_unchanged(
    client: AsyncClient,
    assigned_case_for_agent,
    seeded_device_with_push_reg,
    agent_auth_headers,
):
    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": assigned_case_for_agent.id},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "dispatched"
    assert resp.json().get("qr_payload") is None
