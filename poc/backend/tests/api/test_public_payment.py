"""v2.2 — 业主公开缴费页端点 GET /public/payment/{token}。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


async def _send_link(client, case_id, headers) -> str:
    resp = await client.post(
        f"/api/v1/admin/cases/{case_id}/send-payment-link", headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


@pytest.mark.asyncio
async def test_public_payment_returns_bill(
    client, db_session, seeded_case, admin_auth_headers
):
    """凭有效 token 取账单：含明细、收款信息、业主姓名，不含手机号。"""
    token = await _send_link(client, seeded_case.id, admin_auth_headers)
    resp = await client.get(f"/api/v1/public/payment/{token}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["owner_name"] == "张三"
    assert body["breakdown"]["payable"] is not None
    assert body["payment_mode"] == "property_self"
    # 不得泄露手机号
    assert "phone" not in str(body).lower()


@pytest.mark.asyncio
async def test_public_payment_unknown_token_404(client):
    resp = await client.get("/api/v1/public/payment/nonexistent_token")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_public_payment_expired_token_410(
    client, db_session, seeded_case, admin_auth_headers
):
    from app.models.payment_link import PaymentLink

    token = await _send_link(client, seeded_case.id, admin_auth_headers)
    row = db_session.query(PaymentLink).filter(PaymentLink.token == token).one()
    row.expires_at = datetime.now(UTC) - timedelta(days=1)
    db_session.flush()
    resp = await client.get(f"/api/v1/public/payment/{token}")
    assert resp.status_code == 410
