import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import Base, Tenant, CollectionCase
from app.models.tenant import TenantMinuteUsage


def test_tables_created(engine):
    expected = {
        "tenant", "service_provider", "provider_tenant_contract",
        "tenant_minute_usage", "user_tenant_membership",
        "user_account", "platform_ops_assignment",
        "owner_profile", "project", "collection_case",
        "call_record", "transcript", "analysis_result", "risk_event",
        "work_order", "legal_case",
        "settlement_statement", "dispute_record",
    }
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        ))
        actual = {row[0] for row in result}
    assert expected.issubset(actual), f"Missing tables: {expected - actual}"


def test_tenant_creation(db_session):
    tenant = Tenant(
        name="测试物业",
        admin_phone_enc="encrypted_phone",
        plan="basic",
        monthly_minute_quota=1000,
    )
    db_session.add(tenant)
    db_session.flush()
    assert tenant.id is not None
    assert tenant.is_active is True


def test_case_requires_tenant_id(db_session):
    case = CollectionCase(owner_id=1)  # no tenant_id
    db_session.add(case)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_tenant_minute_usage_unique_per_month(db_session):
    tenant = Tenant(name="配额测试", admin_phone_enc="enc", plan="basic")
    db_session.add(tenant)
    db_session.flush()

    u1 = TenantMinuteUsage(tenant_id=tenant.id, year_month="2026-04", used_minutes=100)
    db_session.add(u1)
    db_session.flush()

    u2 = TenantMinuteUsage(tenant_id=tenant.id, year_month="2026-04", used_minutes=200)
    db_session.add(u2)
    with pytest.raises(IntegrityError):
        db_session.flush()
