"""v1.6.8 — 法务转化两步审批：催收员申请 → 督导/admin 审批 → 创建 Order."""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.fixture
def seeded_packages(db_session):
    """种 4 条平台默认服务包（与 test_legal_conversion.py 同款）。"""
    from app.models.legal_conversion import LegalServicePackage

    pkgs = [
        LegalServicePackage(
            tenant_id=None,
            slug="lawyer_letter",
            package_type="lawyer_letter",
            name="律师函发送",
            price=Decimal("199.00"),
            platform_fee_rate=Decimal("0.30"),
            sort_order=10,
        ),
        LegalServicePackage(
            tenant_id=None,
            slug="mediation",
            package_type="mediation",
            name="诉前调解",
            price=Decimal("399.00"),
            platform_fee_rate=Decimal("0.25"),
            sort_order=20,
        ),
    ]
    for p in pkgs:
        db_session.add(p)
    db_session.flush()
    return pkgs


# ── 1. 催收员提交申请 ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_agent_submit_transfer_legal_creates_request(
    client: AsyncClient,
    db_session,
    seeded_assigned_case,
    agent_auth_headers,
    seeded_member_user,
):
    """催收员 POST /agent/cases/{id}/intent action=transfer_legal → 写入一条 pending request."""
    from app.models.legal_conversion import LegalConversionRequest

    case = seeded_assigned_case
    resp = await client.post(
        f"/api/v1/agent/cases/{case.id}/intent",
        json={"action": "transfer_legal", "note": "业主明确拒绝缴费已 3 次"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["action"] == "transfer_legal"
    assert body["status"] == "queued"

    rows = (
        db_session.query(LegalConversionRequest)
        .filter(LegalConversionRequest.case_id == case.id)
        .all()
    )
    assert len(rows) == 1
    r = rows[0]
    assert r.status == "pending"
    assert r.requester_user_id == seeded_member_user.id
    assert r.requester_role == "agent_internal"
    assert r.reason == "业主明确拒绝缴费已 3 次"
    assert r.tenant_id == case.tenant_id


@pytest.mark.asyncio
async def test_agent_duplicate_transfer_legal_returns_409(
    client: AsyncClient,
    seeded_assigned_case,
    agent_auth_headers,
):
    """同一 case 重复申请 → 409 ERR_REQUEST_PENDING."""
    case = seeded_assigned_case
    r1 = await client.post(
        f"/api/v1/agent/cases/{case.id}/intent",
        json={"action": "transfer_legal", "note": "第一次"},
        headers=agent_auth_headers,
    )
    assert r1.status_code == 201
    r2 = await client.post(
        f"/api/v1/agent/cases/{case.id}/intent",
        json={"action": "transfer_legal", "note": "第二次"},
        headers=agent_auth_headers,
    )
    assert r2.status_code == 409
    assert r2.json()["code"] == "ERR_REQUEST_PENDING"


# ── 2. 列表权限：催收员只看自己 / 督导看本租户全部 ────────────────


@pytest.mark.asyncio
async def test_supervisor_lists_pending_requests(
    client: AsyncClient,
    seeded_assigned_case,
    agent_auth_headers,
    supervisor_auth_headers,
):
    case = seeded_assigned_case
    await client.post(
        f"/api/v1/agent/cases/{case.id}/intent",
        json={"action": "transfer_legal", "note": "理由 A"},
        headers=agent_auth_headers,
    )
    resp = await client.get(
        "/api/v1/legal-conversion-requests?status=pending",
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    found = next((r for r in body["items"] if r["case_id"] == case.id), None)
    assert found is not None
    assert found["status"] == "pending"
    assert found["reason"] == "理由 A"
    assert found["owner_name"] == "张三"  # 来自 seeded_owner
    assert found["amount_owed"] == "3000.00"


@pytest.mark.asyncio
async def test_agent_only_sees_own_requests(
    client: AsyncClient,
    db_session,
    seeded_assigned_case,
    agent_auth_headers,
    seeded_tenant,
    seeded_owner,
):
    """另一个 agent 创建的 request 不应出现在 agent_auth_headers 用户的列表里。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token
    from app.models.case import CollectionCase
    from app.models.legal_conversion import LegalConversionRequest
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    other_user = UserAccount(
        phone_enc=encrypt_phone("13877788888"),
        name="另一个催收员",
        password_hash="x",
        is_active=True,
    )
    db_session.add(other_user)
    db_session.flush()
    db_session.add(
        UserTenantMembership(
            user_id=other_user.id,
            tenant_id=seeded_tenant.id,
            role="agent_internal",
            source_type="INTERNAL",
            is_active=True,
        )
    )
    other_case = CollectionCase(
        tenant_id=seeded_tenant.id,
        owner_id=seeded_owner.id,
        pool_type="public",
        stage="new",
        amount_owed=Decimal("500.00"),
        months_overdue=1,
        priority_score=300,
        assigned_to=other_user.id,
    )
    db_session.add(other_case)
    db_session.flush()
    db_session.add(
        LegalConversionRequest(
            tenant_id=seeded_tenant.id,
            case_id=other_case.id,
            requester_user_id=other_user.id,
            requester_role="agent_internal",
            reason="他的理由",
            status="pending",
        )
    )
    db_session.commit()

    # current agent 提自己 case 的申请
    case = seeded_assigned_case
    await client.post(
        f"/api/v1/agent/cases/{case.id}/intent",
        json={"action": "transfer_legal", "note": "我的理由"},
        headers=agent_auth_headers,
    )

    resp = await client.get(
        "/api/v1/legal-conversion-requests",
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    case_ids = {r["case_id"] for r in resp.json()["items"]}
    assert case.id in case_ids
    assert other_case.id not in case_ids


# ── 3. 督导批准：写入 approved + 创建 Order ─────────────────────────


@pytest.mark.asyncio
async def test_supervisor_approve_creates_order(
    client: AsyncClient,
    db_session,
    seeded_assigned_case,
    seeded_packages,
    agent_auth_headers,
    supervisor_auth_headers,
):
    from app.models.legal_conversion import (
        LegalConversionOrder,
        LegalConversionRequest,
    )

    case = seeded_assigned_case
    pkg = seeded_packages[0]

    # 1) 催收员申请
    await client.post(
        f"/api/v1/agent/cases/{case.id}/intent",
        json={"action": "transfer_legal", "note": "请审批"},
        headers=agent_auth_headers,
    )
    request_row = (
        db_session.query(LegalConversionRequest)
        .filter(LegalConversionRequest.case_id == case.id)
        .one()
    )

    # 2) 督导批准
    resp = await client.post(
        f"/api/v1/legal-conversion-requests/{request_row.id}/approve",
        json={"package_id": pkg.id, "notes": "情况属实，建议律师函"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "approved"
    assert body["related_order_id"] is not None
    assert body["reviewer_role"] == "supervisor"
    assert body["reviewed_at"] is not None

    # 3) DB 校验：request 状态 + Order 已创建
    db_session.expire_all()
    request_row = db_session.get(LegalConversionRequest, request_row.id)
    assert request_row.status == "approved"
    order = db_session.get(LegalConversionOrder, request_row.related_order_id)
    assert order is not None
    assert order.case_id == case.id
    assert order.package_id == pkg.id
    # v1.9.0 — supervisor 审批通过后订单进物业法务内部处理（不再直接 pending 等 admin 撮合律所）
    assert order.status == "internal_processing"


@pytest.mark.asyncio
async def test_approve_already_approved_returns_409(
    client: AsyncClient,
    db_session,
    seeded_assigned_case,
    seeded_packages,
    agent_auth_headers,
    supervisor_auth_headers,
):
    case = seeded_assigned_case
    pkg = seeded_packages[0]
    await client.post(
        f"/api/v1/agent/cases/{case.id}/intent",
        json={"action": "transfer_legal"},
        headers=agent_auth_headers,
    )
    from app.models.legal_conversion import LegalConversionRequest
    rid = db_session.query(LegalConversionRequest).filter(
        LegalConversionRequest.case_id == case.id
    ).one().id
    r1 = await client.post(
        f"/api/v1/legal-conversion-requests/{rid}/approve",
        json={"package_id": pkg.id},
        headers=supervisor_auth_headers,
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"/api/v1/legal-conversion-requests/{rid}/approve",
        json={"package_id": pkg.id},
        headers=supervisor_auth_headers,
    )
    assert r2.status_code == 409
    assert r2.json()["code"] == "ERR_INVALID_STATUS"


# ── 4. 督导驳回 ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_supervisor_reject_writes_reason(
    client: AsyncClient,
    db_session,
    seeded_assigned_case,
    agent_auth_headers,
    supervisor_auth_headers,
):
    from app.models.legal_conversion import LegalConversionRequest

    case = seeded_assigned_case
    await client.post(
        f"/api/v1/agent/cases/{case.id}/intent",
        json={"action": "transfer_legal"},
        headers=agent_auth_headers,
    )
    rid = db_session.query(LegalConversionRequest).filter(
        LegalConversionRequest.case_id == case.id
    ).one().id

    resp = await client.post(
        f"/api/v1/legal-conversion-requests/{rid}/reject",
        json={"reason": "催收次数不足，请继续协商"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["reviewer_note"] == "催收次数不足，请继续协商"
    assert body["related_order_id"] is None


@pytest.mark.asyncio
async def test_reject_empty_reason_returns_422(
    client: AsyncClient,
    db_session,
    seeded_assigned_case,
    agent_auth_headers,
    supervisor_auth_headers,
):
    from app.models.legal_conversion import LegalConversionRequest

    case = seeded_assigned_case
    await client.post(
        f"/api/v1/agent/cases/{case.id}/intent",
        json={"action": "transfer_legal"},
        headers=agent_auth_headers,
    )
    rid = db_session.query(LegalConversionRequest).filter(
        LegalConversionRequest.case_id == case.id
    ).one().id

    resp = await client.post(
        f"/api/v1/legal-conversion-requests/{rid}/reject",
        json={"reason": ""},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 422


# ── 5. 跨租户隔离 ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cross_tenant_request_returns_404(
    client: AsyncClient,
    db_session,
    seeded_supervisor_user,
    seeded_assigned_case,
    agent_auth_headers,
):
    """另一个 tenant 的督导用 token 看本 tenant 的 request → 404."""
    from app.core.security import create_access_token
    from app.models.legal_conversion import LegalConversionRequest

    case = seeded_assigned_case
    await client.post(
        f"/api/v1/agent/cases/{case.id}/intent",
        json={"action": "transfer_legal"},
        headers=agent_auth_headers,
    )
    rid = db_session.query(LegalConversionRequest).filter(
        LegalConversionRequest.case_id == case.id
    ).one().id

    # 用一个虚拟 tenant_id 的 supervisor token（用户存在但 tenant 不匹配）
    foreign_token = create_access_token({
        "sub": str(seeded_supervisor_user.id),
        "user_id": seeded_supervisor_user.id,
        "tenant_id": 99999,  # 不存在的租户
        "role": "supervisor",
        "scope": "tenant:99999",
    })
    headers = {"Authorization": f"Bearer {foreign_token}"}

    resp = await client.post(
        f"/api/v1/legal-conversion-requests/{rid}/reject",
        json={"reason": "试图越权"},
        headers=headers,
    )
    assert resp.status_code == 404
