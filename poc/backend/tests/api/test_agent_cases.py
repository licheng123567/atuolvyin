import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_agent_sees_public_unassigned_cases(
    client: AsyncClient, agent_auth_headers, seeded_case
):
    resp = await client.get("/api/v1/agent/cases", headers=agent_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    ids = [item["id"] for item in data["items"]]
    assert seeded_case.id in ids  # seeded_case is public + unassigned


@pytest.mark.asyncio
async def test_agent_sees_own_private_cases(
    client: AsyncClient,
    agent_auth_headers,
    admin_auth_headers,
    seeded_case,
    seeded_member_user,
):
    # Assign case to agent
    await client.post(
        "/api/v1/admin/cases/assign",
        json={"case_ids": [seeded_case.id], "assign_to": seeded_member_user.id},
        headers=admin_auth_headers,
    )
    resp = await client.get("/api/v1/agent/cases", headers=agent_auth_headers)
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert seeded_case.id in ids
    matching = next(i for i in resp.json()["items"] if i["id"] == seeded_case.id)
    assert matching["pool_type"] == "private"
    assert matching["assigned_to"] == seeded_member_user.id


@pytest.mark.asyncio
async def test_claim_case_from_public_pool(
    client: AsyncClient, agent_auth_headers, seeded_case
):
    resp = await client.post(
        f"/api/v1/agent/cases/{seeded_case.id}/claim",
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pool_type"] == "private"
    assert data["assigned_to"] is not None


@pytest.mark.asyncio
async def test_claim_already_claimed_case(
    client: AsyncClient,
    agent_auth_headers,
    admin_auth_headers,
    seeded_case,
    seeded_member_user,
):
    # Assign to agent first
    await client.post(
        "/api/v1/admin/cases/assign",
        json={"case_ids": [seeded_case.id], "assign_to": seeded_member_user.id},
        headers=admin_auth_headers,
    )
    # Agent tries to claim an already assigned case
    resp = await client.post(
        f"/api/v1/agent/cases/{seeded_case.id}/claim",
        headers=agent_auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_ALREADY_CLAIMED"


@pytest.mark.asyncio
async def test_claim_nonexistent_case(client: AsyncClient, agent_auth_headers):
    resp = await client.post(
        "/api/v1/agent/cases/999999/claim", headers=agent_auth_headers
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ERR_NOT_FOUND"


@pytest.mark.asyncio
async def test_agent_cases_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/agent/cases")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_claim_requires_auth(client: AsyncClient, seeded_case):
    resp = await client.post(f"/api/v1/agent/cases/{seeded_case.id}/claim")
    assert resp.status_code == 401


# ── v1.6.9 — 公海池 quota + release ──────────────────────────────


@pytest.mark.asyncio
async def test_pool_quota_default_50(
    client: AsyncClient, agent_auth_headers
):
    resp = await client.get("/api/v1/agent/me/pool-quota", headers=agent_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["claim_max"] == 50
    assert body["held_open"] == 0
    assert body["can_claim_more"] is True
    assert body["remaining"] == 50


@pytest.mark.asyncio
async def test_claim_blocked_when_at_limit(
    client: AsyncClient, db_session, agent_auth_headers, seeded_case,
    seeded_member_user, seeded_tenant,
):
    """把 quota 设到 1，并预先分配 1 件给 agent → claim 公海应 409."""
    from app.models.settings import TenantSettings
    db_session.add(TenantSettings(tenant_id=seeded_tenant.id, public_pool_claim_max=1))
    # 直接把 seeded_case 分给 agent（变成私海持有）
    seeded_case.assigned_to = seeded_member_user.id
    seeded_case.pool_type = "private"
    db_session.flush()
    # 再造一个公海案件
    from decimal import Decimal
    from app.models.case import CollectionCase
    other = CollectionCase(
        tenant_id=seeded_tenant.id, owner_id=seeded_case.owner_id,
        pool_type="public", stage="new",
        amount_owed=Decimal("100"), priority_score=100,
    )
    db_session.add(other)
    db_session.commit()
    # 试图 claim → 上限触达
    resp = await client.post(
        f"/api/v1/agent/cases/{other.id}/claim", headers=agent_auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ERR_CLAIM_LIMIT"


@pytest.mark.asyncio
async def test_release_own_case_back_to_pool(
    client: AsyncClient, db_session, agent_auth_headers, seeded_case,
    seeded_member_user,
):
    """v0.9.0 — release 必填 reason(写入 audit_log payload)."""
    seeded_case.assigned_to = seeded_member_user.id
    seeded_case.pool_type = "private"
    db_session.commit()
    resp = await client.post(
        f"/api/v1/agent/cases/{seeded_case.id}/release",
        headers=agent_auth_headers,
        json={"reason": "5 次拨打未接"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["pool_type"] == "public"
    assert body["assigned_to"] is None


@pytest.mark.asyncio
async def test_release_missing_reason_returns_422(
    client: AsyncClient, db_session, agent_auth_headers, seeded_case,
    seeded_member_user,
):
    """v0.9.0 — 不传 reason 时 422(必填校验)。"""
    seeded_case.assigned_to = seeded_member_user.id
    seeded_case.pool_type = "private"
    db_session.commit()
    resp = await client.post(
        f"/api/v1/agent/cases/{seeded_case.id}/release",
        headers=agent_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_release_others_case_returns_403(
    client: AsyncClient, db_session, agent_auth_headers, seeded_case,
    seeded_user,
):
    """seeded_case 分给另一个用户(admin),agent 试图 release → 403."""
    seeded_case.assigned_to = seeded_user.id  # admin user, not agent
    seeded_case.pool_type = "private"
    db_session.commit()
    resp = await client.post(
        f"/api/v1/agent/cases/{seeded_case.id}/release",
        headers=agent_auth_headers,
        json={"reason": "尝试越权释放"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_NOT_YOURS"


# ─── v0.5.6 标记承诺缴费(stage='promised' + 3 结构化字段) ──────────────────


@pytest.mark.asyncio
async def test_mark_promised_with_structured_fields(
    client: AsyncClient, db_session, agent_auth_headers, seeded_case, seeded_member_user,
):
    """v0.5.6 — 标记承诺缴费时 promise_content / promise_amount / promise_due_at
    全部应写入 case 行,并出现在 audit log payload。"""
    from decimal import Decimal
    seeded_case.assigned_to = seeded_member_user.id
    seeded_case.pool_type = "private"
    db_session.commit()
    resp = await client.patch(
        f"/api/v1/agent/cases/{seeded_case.id}/stage",
        json={
            "stage": "promised",
            "note": "业主承诺端午节前缴清",
            "promise_content": "全额缴清",
            "promise_amount": "5000.00",
            "promise_due_at": "2026-06-10T00:00:00Z",
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200

    # 持久化校验
    from app.models.case import CollectionCase
    db_session.expire_all()
    refreshed = db_session.get(CollectionCase, seeded_case.id)
    assert refreshed.stage == "promised"
    assert refreshed.promise_content == "全额缴清"
    assert refreshed.promise_amount == Decimal("5000.00")
    assert refreshed.promise_due_at is not None

    # AuditLog payload 应包含 3 字段
    from sqlalchemy import select
    from app.models.audit import AuditLog
    logs = db_session.execute(
        select(AuditLog).where(
            AuditLog.target_type == "collection_case",
            AuditLog.target_id == seeded_case.id,
        )
    ).scalars().all()
    promised_log = next(
        (l for l in logs if (l.payload or {}).get("to") == "promised"),
        None,
    )
    assert promised_log is not None
    assert promised_log.payload.get("promise_content") == "全额缴清"
    assert promised_log.payload.get("promise_amount") == "5000.00"
    assert "promise_due_at" in promised_log.payload


@pytest.mark.asyncio
async def test_mark_promised_without_amount_allowed(
    client: AsyncClient, db_session, agent_auth_headers, seeded_case, seeded_member_user,
):
    """v0.5.6 — 业主只口头承诺不报金额时,promise_amount 可空。"""
    seeded_case.assigned_to = seeded_member_user.id
    seeded_case.pool_type = "private"
    db_session.commit()
    resp = await client.patch(
        f"/api/v1/agent/cases/{seeded_case.id}/stage",
        json={
            "stage": "promised",
            "promise_content": "分期 3 次,具体金额待商定",
            "promise_due_at": "2026-07-01T00:00:00Z",
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200

    from app.models.case import CollectionCase
    db_session.expire_all()
    refreshed = db_session.get(CollectionCase, seeded_case.id)
    assert refreshed.promise_content == "分期 3 次,具体金额待商定"
    assert refreshed.promise_amount is None


@pytest.mark.asyncio
async def test_other_stages_dont_touch_promise_fields(
    client: AsyncClient, db_session, agent_auth_headers, seeded_case, seeded_member_user,
):
    """v0.5.6 — 切到其他阶段(in_progress / paid / closed)时,即使 body 里带了
    promise_* 字段也应忽略,不写到 case 行(避免误清空已记录的承诺)。"""
    from decimal import Decimal
    seeded_case.assigned_to = seeded_member_user.id
    seeded_case.pool_type = "private"
    # 先种一个已有的承诺
    seeded_case.promise_content = "原承诺:5000"
    seeded_case.promise_amount = Decimal("5000.00")
    db_session.commit()

    resp = await client.patch(
        f"/api/v1/agent/cases/{seeded_case.id}/stage",
        json={
            "stage": "in_progress",
            "promise_content": "不该写入",  # 应被忽略
            "promise_amount": "9999.00",  # 应被忽略
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200

    from app.models.case import CollectionCase
    db_session.expire_all()
    refreshed = db_session.get(CollectionCase, seeded_case.id)
    assert refreshed.stage == "in_progress"
    # 原承诺保留不变
    assert refreshed.promise_content == "原承诺:5000"
    assert refreshed.promise_amount == Decimal("5000.00")
