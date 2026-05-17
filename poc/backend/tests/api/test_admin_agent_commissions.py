"""§9.2 Task 5 — /admin/agent-commissions 逐案按项目率 + 扣减免。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest


def _project(db_session, tenant_id, name, internal_rate):
    from app.models.case import Project

    p = Project(tenant_id=tenant_id, name=name, internal_agent_commission_rate=internal_rate)
    db_session.add(p)
    db_session.flush()
    return p


def _paid_case(db_session, tenant_id, owner_id, agent_id, project_id, amount_owed):
    from app.models.case import CollectionCase

    case = CollectionCase(
        tenant_id=tenant_id,
        owner_id=owner_id,
        project_id=project_id,
        assigned_to=agent_id,
        pool_type="public",
        stage="paid",
        amount_owed=Decimal(amount_owed),
        months_overdue=3,
        priority_score=1000,
        updated_at=datetime(2026, 5, 15, tzinfo=UTC),
    )
    db_session.add(case)
    db_session.flush()
    return case


def _executed_offer(db_session, tenant_id, case_id, proposed):
    from app.models.discount_offer import DiscountOffer

    db_session.add(
        DiscountOffer(
            tenant_id=tenant_id,
            case_id=case_id,
            applicant_user_id=None,
            applicant_role="agent",
            offer_type="principal_discount",
            original_amount=Decimal("1000.00"),
            proposed_amount=Decimal(proposed),
            discount_pct=10,
            reason="内勤佣金测试减免",
            status="executed",
            approver_role_required="supervisor",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            audit_trail=[],
        )
    )
    db_session.flush()


@pytest.mark.asyncio
async def test_agent_commission_per_case_rate_and_discount(
    client, db_session, seeded_tenant, seeded_owner, seeded_member_user, admin_auth_headers
):
    # 项目 P1：内勤率 0.08；P2：NULL → 默认 0.05
    p1 = _project(db_session, seeded_tenant.id, "佣金项目甲", Decimal("0.0800"))
    p2 = _project(db_session, seeded_tenant.id, "佣金项目乙", None)
    # C1：欠 1000，有已执行减免 → 实收 600；归 P1
    c1 = _paid_case(
        db_session, seeded_tenant.id, seeded_owner.id, seeded_member_user.id, p1.id, "1000.00"
    )
    _executed_offer(db_session, seeded_tenant.id, c1.id, "600.00")
    # C2：欠 2000，无减免；归 P2
    _paid_case(
        db_session, seeded_tenant.id, seeded_owner.id, seeded_member_user.id, p2.id, "2000.00"
    )

    resp = await client.get(
        "/api/v1/admin/agent-commissions?year_month=2026-05", headers=admin_auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    item = next(it for it in body["items"] if it["user_id"] == seeded_member_user.id)
    assert item["paid_case_count"] == 2
    # base = 实收 600 + 2000 = 2600
    assert Decimal(item["base_amount"]) == Decimal("2600.00")
    # commission = (600*0.08).q(.01) + (2000*0.05).q(.01) = 48.00 + 100.00
    assert Decimal(item["commission"]) == Decimal("148.00")
    assert Decimal(str(body["total_base"])) == Decimal("2600.00")
    assert Decimal(str(body["total_commission"])) == Decimal("148.00")


@pytest.mark.asyncio
async def test_agent_commission_full_waiver_zero_collected(
    client, db_session, seeded_tenant, seeded_owner, seeded_member_user, admin_auth_headers
):
    """§9.2-C 回归：全额减免（实收 0）的案件，佣金基数贡献为 0，不按原欠款发佣金。"""
    p = _project(db_session, seeded_tenant.id, "全额减免项目", Decimal("0.0800"))
    c = _paid_case(
        db_session, seeded_tenant.id, seeded_owner.id, seeded_member_user.id, p.id, "1000.00"
    )
    _executed_offer(db_session, seeded_tenant.id, c.id, "0.00")  # 全额减免，业主实缴 0

    resp = await client.get(
        "/api/v1/admin/agent-commissions?year_month=2026-05", headers=admin_auth_headers
    )
    assert resp.status_code == 200, resp.text
    item = next(it for it in resp.json()["items"] if it["user_id"] == seeded_member_user.id)
    assert item["paid_case_count"] == 1
    assert Decimal(item["base_amount"]) == Decimal("0.00")
    assert Decimal(item["commission"]) == Decimal("0.00")
