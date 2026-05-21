"""v2.2 — compute_payable：案件应付额 = 应缴 − 已审批减免。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal


def _discount_offer(db_session, case, *, status, original, proposed, approved_days_ago=0):
    from app.models.discount_offer import DiscountOffer

    now = datetime.now(UTC)
    offer = DiscountOffer(
        tenant_id=case.tenant_id,
        case_id=case.id,
        applicant_user_id=None,
        applicant_role="agent",
        offer_type="principal_discount",
        original_amount=Decimal(original),
        proposed_amount=Decimal(proposed),
        discount_pct=10,
        reason="测试减免",
        status=status,
        approver_role_required="supervisor",
        approved_at=now - timedelta(days=approved_days_ago) if status == "approved" else None,
        expires_at=now + timedelta(days=7),
    )
    db_session.add(offer)
    db_session.flush()
    return offer


def test_no_discount_payable_equals_owed(db_session, seeded_case):
    from app.services.payment_link import compute_payable

    b = compute_payable(db_session, seeded_case)
    assert b.original == seeded_case.amount_owed
    assert b.waived == Decimal("0")
    assert b.payable == seeded_case.amount_owed
    assert b.has_pending is False


def test_approved_discount_reduces_payable(db_session, seeded_case):
    from app.services.payment_link import compute_payable

    _discount_offer(
        db_session, seeded_case, status="approved",
        original="3000.00", proposed="2400.00",
    )
    b = compute_payable(db_session, seeded_case)
    assert b.payable == Decimal("2400.00")
    assert b.waived == seeded_case.amount_owed - Decimal("2400.00")


def test_pending_discount_does_not_reduce_but_flags(db_session, seeded_case):
    from app.services.payment_link import compute_payable

    _discount_offer(
        db_session, seeded_case, status="pending_supervisor",
        original="3000.00", proposed="2400.00",
    )
    b = compute_payable(db_session, seeded_case)
    assert b.payable == seeded_case.amount_owed  # pending 不抵扣
    assert b.has_pending is True


def test_expired_offer_ignored(db_session, seeded_case):
    from app.services.payment_link import compute_payable

    offer = _discount_offer(
        db_session, seeded_case, status="approved",
        original="3000.00", proposed="2000.00",
    )
    offer.expires_at = datetime.now(UTC) - timedelta(days=1)  # 已过期
    db_session.flush()
    b = compute_payable(db_session, seeded_case)
    assert b.payable == seeded_case.amount_owed  # 过期减免不计


def test_breakdown_includes_principal_and_late_fee(db_session, seeded_case):
    from app.services.payment_link import compute_payable

    seeded_case.principal_amount = Decimal("2800.00")
    seeded_case.late_fee_amount = Decimal("200.00")
    db_session.flush()
    b = compute_payable(db_session, seeded_case)
    assert b.principal == Decimal("2800.00")
    assert b.late_fee == Decimal("200.00")
