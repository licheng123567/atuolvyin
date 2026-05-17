"""§9.2 Task 4 — app/services/commission.py 单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal


def _offer(db_session, tenant_id, case_id, *, proposed, status):
    from app.models.discount_offer import DiscountOffer

    offer = DiscountOffer(
        tenant_id=tenant_id,
        case_id=case_id,
        applicant_user_id=None,
        applicant_role="agent",
        offer_type="principal_discount",
        original_amount=Decimal("1000.00"),
        proposed_amount=Decimal(proposed),
        discount_pct=10,
        reason="commission service 测试减免",
        status=status,
        approver_role_required="supervisor",
        expires_at=datetime.now(UTC) + timedelta(days=7),
        audit_trail=[],
    )
    db_session.add(offer)
    db_session.flush()
    return offer


def test_executed_discount_amounts_empty_list(db_session, seeded_tenant):
    from app.services.commission import executed_discount_amounts

    assert executed_discount_amounts(db_session, seeded_tenant.id, []) == {}


def test_executed_discount_amounts_returns_proposed_for_executed(
    db_session, seeded_tenant, seeded_case
):
    from app.services.commission import executed_discount_amounts

    _offer(db_session, seeded_tenant.id, seeded_case.id, proposed="600.00", status="executed")
    result = executed_discount_amounts(db_session, seeded_tenant.id, [seeded_case.id])
    assert result == {seeded_case.id: Decimal("600.00")}


def test_executed_discount_amounts_skips_non_executed(db_session, seeded_tenant, seeded_case):
    from app.services.commission import executed_discount_amounts

    _offer(db_session, seeded_tenant.id, seeded_case.id, proposed="600.00", status="approved")
    assert executed_discount_amounts(db_session, seeded_tenant.id, [seeded_case.id]) == {}


def test_executed_discount_amounts_latest_wins(db_session, seeded_tenant, seeded_case):
    from app.services.commission import executed_discount_amounts

    _offer(db_session, seeded_tenant.id, seeded_case.id, proposed="600.00", status="executed")
    _offer(db_session, seeded_tenant.id, seeded_case.id, proposed="550.00", status="executed")
    result = executed_discount_amounts(db_session, seeded_tenant.id, [seeded_case.id])
    assert result == {seeded_case.id: Decimal("550.00")}


def test_internal_agent_rate(db_session, seeded_tenant):
    from app.models.case import Project
    from app.services.commission import DEFAULT_COMMISSION_RATE, internal_agent_rate

    p_rate = Project(
        tenant_id=seeded_tenant.id,
        name="有内勤率项目",
        internal_agent_commission_rate=Decimal("0.0900"),
    )
    p_null = Project(tenant_id=seeded_tenant.id, name="无内勤率项目")
    db_session.add_all([p_rate, p_null])
    db_session.flush()

    assert internal_agent_rate(p_rate) == Decimal("0.0900")
    assert internal_agent_rate(p_null) == DEFAULT_COMMISSION_RATE
    assert internal_agent_rate(None) == DEFAULT_COMMISSION_RATE


def test_provider_agent_rate(db_session, seeded_tenant):
    from app.models.case import Project
    from app.services.commission import DEFAULT_COMMISSION_RATE, provider_agent_rate

    p_rate = Project(
        tenant_id=seeded_tenant.id,
        name="有服务商率项目",
        provider_agent_commission_rate=Decimal("0.1500"),
    )
    p_null = Project(tenant_id=seeded_tenant.id, name="无服务商率项目")
    db_session.add_all([p_rate, p_null])
    db_session.flush()

    assert provider_agent_rate(p_rate) == Decimal("0.1500")
    assert provider_agent_rate(p_null) == DEFAULT_COMMISSION_RATE
    assert provider_agent_rate(None) == DEFAULT_COMMISSION_RATE
