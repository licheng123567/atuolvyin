"""Sprint 8.2 — script effectiveness aggregation (PRD §3.11).

Validates that GET /api/v1/admin/scripts/effectiveness aggregates
SuggestionFeedback rows into adoption rate, supervisor good ratio,
composite score and grade — scoped per tenant and time window.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def seeded_template(db_session, seeded_tenant):
    from app.models.script import ScriptTemplate

    t = ScriptTemplate(
        tenant_id=seeded_tenant.id,
        title="经济困难话术 A",
        trigger_intent="经济困难",
        content="尊敬的业主...",
        version=1,
        is_active=True,
    )
    db_session.add(t)
    db_session.flush()
    return t


@pytest.fixture
def secondary_template(db_session, seeded_tenant):
    from app.models.script import ScriptTemplate

    t = ScriptTemplate(
        tenant_id=seeded_tenant.id,
        title="服务不满话术 X",
        trigger_intent="服务不满",
        content="非常抱歉...",
        version=1,
        is_active=True,
    )
    db_session.add(t)
    db_session.flush()
    return t


def _make_call(db_session, tenant, caller_user):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=tenant.id,
        caller_user_id=caller_user.id,
        callee_phone_enc=encrypt_phone("13700000000"),
        initiated_by="app",
        status="processed",
    )
    db_session.add(call)
    db_session.flush()
    return call


def _make_feedback(
    db_session,
    *,
    call,
    user,
    template_id: int,
    suggestion_id: str,
    action: str,
    supervisor_label: str | None = None,
    created_at: datetime | None = None,
):
    from app.models.call import SuggestionFeedback

    f = SuggestionFeedback(
        call_id=call.id,
        suggestion_id=suggestion_id,
        user_id=user.id,
        action=action,
        suggestion_text="text",
        supervisor_label=supervisor_label,
        script_template_id=template_id,
        created_at=created_at or datetime.now(UTC),
    )
    db_session.add(f)
    db_session.flush()
    return f


# ── tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_effectiveness_empty_when_no_feedback(
    client: AsyncClient, seeded_template, admin_auth_headers
):
    resp = await client.get(
        "/api/v1/admin/scripts/effectiveness", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["period_days"] == 30
    items = data["items"]
    item = next(i for i in items if i["template_id"] == seeded_template.id)
    assert item["total_shown"] == 0
    assert item["adoption_rate"] is None
    assert item["composite_grade"] is None


@pytest.mark.asyncio
async def test_effectiveness_computes_adoption_rate(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_template,
    seeded_member_user,
    admin_auth_headers,
):
    call = _make_call(db_session, seeded_tenant, seeded_member_user)
    _make_feedback(
        db_session,
        call=call,
        user=seeded_member_user,
        template_id=seeded_template.id,
        suggestion_id="s1",
        action="adopt",
    )
    _make_feedback(
        db_session,
        call=call,
        user=seeded_member_user,
        template_id=seeded_template.id,
        suggestion_id="s2",
        action="adopt",
    )
    _make_feedback(
        db_session,
        call=call,
        user=seeded_member_user,
        template_id=seeded_template.id,
        suggestion_id="s3",
        action="ignore",
    )

    resp = await client.get(
        "/api/v1/admin/scripts/effectiveness", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    item = next(
        i for i in resp.json()["items"] if i["template_id"] == seeded_template.id
    )
    assert item["total_shown"] == 3
    assert item["total_adopted"] == 2
    assert item["adoption_rate"] == pytest.approx(2 / 3, abs=1e-3)
    # No supervisor labels yet
    assert item["good_ratio"] is None
    # Composite uses adoption only when no supervised feedback
    assert item["composite_score"] == pytest.approx(2 / 3, abs=1e-3)
    assert item["composite_grade"] == "B"  # 0.667 falls in [0.6, 0.8)


@pytest.mark.asyncio
async def test_effectiveness_combines_adoption_and_good_ratio(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_template,
    seeded_member_user,
    admin_auth_headers,
):
    call = _make_call(db_session, seeded_tenant, seeded_member_user)
    # 4 of 5 adopted; 3 of 4 labelled good
    for i, action in enumerate(["adopt"] * 4 + ["ignore"]):
        _make_feedback(
            db_session,
            call=call,
            user=seeded_member_user,
            template_id=seeded_template.id,
            suggestion_id=f"s{i}",
            action=action,
            supervisor_label=("good" if i < 3 else "bad" if i == 3 else None),
        )

    resp = await client.get(
        "/api/v1/admin/scripts/effectiveness", headers=admin_auth_headers
    )
    item = next(
        i for i in resp.json()["items"] if i["template_id"] == seeded_template.id
    )
    assert item["adoption_rate"] == pytest.approx(0.8, abs=1e-3)
    assert item["good_ratio"] == pytest.approx(3 / 4, abs=1e-3)
    # 0.6 * 0.8 + 0.4 * 0.75 = 0.78 → B
    assert item["composite_score"] == pytest.approx(0.78, abs=1e-3)
    assert item["composite_grade"] == "B"


@pytest.mark.asyncio
async def test_effectiveness_excludes_old_feedback(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_template,
    seeded_member_user,
    admin_auth_headers,
):
    call = _make_call(db_session, seeded_tenant, seeded_member_user)
    # 100 days ago — outside default 30-day window
    _make_feedback(
        db_session,
        call=call,
        user=seeded_member_user,
        template_id=seeded_template.id,
        suggestion_id="s_old",
        action="adopt",
        created_at=datetime.now(UTC) - timedelta(days=100),
    )

    resp = await client.get(
        "/api/v1/admin/scripts/effectiveness", headers=admin_auth_headers
    )
    item = next(
        i for i in resp.json()["items"] if i["template_id"] == seeded_template.id
    )
    assert item["total_shown"] == 0


@pytest.mark.asyncio
async def test_effectiveness_filters_by_intent(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_template,
    secondary_template,
    seeded_member_user,
    admin_auth_headers,
):
    call = _make_call(db_session, seeded_tenant, seeded_member_user)
    _make_feedback(
        db_session,
        call=call,
        user=seeded_member_user,
        template_id=secondary_template.id,
        suggestion_id="s1",
        action="adopt",
    )

    resp = await client.get(
        "/api/v1/admin/scripts/effectiveness?intent=经济困难",
        headers=admin_auth_headers,
    )
    items = resp.json()["items"]
    template_ids = {i["template_id"] for i in items}
    assert seeded_template.id in template_ids
    assert secondary_template.id not in template_ids


@pytest.mark.asyncio
async def test_effectiveness_excludes_other_tenant_feedback(
    client: AsyncClient,
    db_session,
    seeded_template,
    seeded_member_user,
    admin_auth_headers,
):
    """Feedback rows from a CallRecord belonging to a different tenant
    must not contribute to this tenant's adoption stats."""
    from app.core.crypto import encrypt_phone
    from app.models.tenant import Tenant

    other_tenant = Tenant(
        name="其他租户",
        admin_phone_enc=encrypt_phone("13900000099"),
        plan="trial",
        is_active=True,
    )
    db_session.add(other_tenant)
    db_session.flush()

    call_other = _make_call(db_session, other_tenant, seeded_member_user)
    _make_feedback(
        db_session,
        call=call_other,
        user=seeded_member_user,
        template_id=seeded_template.id,
        suggestion_id="s_other",
        action="adopt",
    )

    resp = await client.get(
        "/api/v1/admin/scripts/effectiveness", headers=admin_auth_headers
    )
    item = next(
        i for i in resp.json()["items"] if i["template_id"] == seeded_template.id
    )
    assert item["total_shown"] == 0


@pytest.mark.asyncio
async def test_effectiveness_requires_admin(
    client: AsyncClient, ops_auth_headers
):
    resp = await client.get(
        "/api/v1/admin/scripts/effectiveness", headers=ops_auth_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_effectiveness_period_days_validation(
    client: AsyncClient, admin_auth_headers
):
    resp = await client.get(
        "/api/v1/admin/scripts/effectiveness?period_days=0",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422
