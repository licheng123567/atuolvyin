"""§9.2 Task 1 — DiscountOffer.provider_id + Project 佣金率两列 round-trip。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.crypto import encrypt_phone


def _make_provider(db_session):
    from app.models.tenant import ServiceProvider

    p = ServiceProvider(
        name="测试律所92",
        provider_type="legal",
        admin_phone_enc=encrypt_phone("13900092001"),
        is_active=True,
        audit_status="approved",
    )
    db_session.add(p)
    db_session.flush()
    return p


def test_discount_offer_provider_id_round_trip(db_session, seeded_tenant, seeded_case):
    from app.models.discount_offer import DiscountOffer

    provider = _make_provider(db_session)
    offer = DiscountOffer(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        provider_id=provider.id,
        applicant_user_id=None,
        applicant_role="agent",
        offer_type="principal_discount",
        original_amount=Decimal("1000.00"),
        proposed_amount=Decimal("800.00"),
        discount_pct=20,
        reason="家庭困难，申请减免",
        status="pending_supervisor",
        approver_role_required="supervisor",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(offer)
    db_session.flush()
    db_session.refresh(offer)

    got = db_session.get(DiscountOffer, offer.id)
    assert got is not None
    assert got.provider_id == provider.id


def test_discount_offer_provider_id_defaults_null(db_session, seeded_tenant, seeded_case):
    from app.models.discount_offer import DiscountOffer

    offer = DiscountOffer(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        applicant_user_id=None,
        applicant_role="agent",
        offer_type="principal_discount",
        original_amount=Decimal("500.00"),
        proposed_amount=Decimal("500.00"),
        discount_pct=0,
        reason="物业内勤发起减免",
        status="approved",
        approver_role_required="supervisor",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(offer)
    db_session.flush()
    db_session.refresh(offer)
    assert offer.provider_id is None


def test_project_commission_rate_columns_round_trip(db_session, seeded_tenant):
    from app.models.case import Project

    project = Project(
        tenant_id=seeded_tenant.id,
        name="§9.2 佣金率测试项目",
        internal_agent_commission_rate=Decimal("0.0800"),
        provider_agent_commission_rate=Decimal("0.1200"),
    )
    db_session.add(project)
    db_session.flush()
    db_session.refresh(project)

    got = db_session.get(Project, project.id)
    assert got.internal_agent_commission_rate == Decimal("0.0800")
    assert got.provider_agent_commission_rate == Decimal("0.1200")


def test_project_commission_rate_columns_default_null(db_session, seeded_tenant):
    from app.models.case import Project

    project = Project(tenant_id=seeded_tenant.id, name="§9.2 无佣金率项目")
    db_session.add(project)
    db_session.flush()
    db_session.refresh(project)
    assert project.internal_agent_commission_rate is None
    assert project.provider_agent_commission_rate is None
