import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def test_role_check_rejects_legacy_value(db_session):
    """迁移后非法旧角色值被 CHECK 拒绝。"""
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO user_tenant_membership (user_id, tenant_id, role, is_active) "
                "VALUES (1, 1, 'provider_admin', true)"
            )
        )
        db_session.flush()


def test_work_mode_check_requires_agent(db_session):
    """work_mode 非空但 role 不是 agent → 被拒。"""
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO user_tenant_membership (user_id, tenant_id, role, work_mode, is_active) "
                "VALUES (1, 1, 'supervisor', 'internal', true)"
            )
        )
        db_session.flush()


def test_platform_role_check_rejects_unknown(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(
            text("INSERT INTO user_account (phone_enc, name, password_hash, platform_role) "
                 "VALUES ('x', 'x', 'x', 'god')")
        )
        db_session.flush()


def test_source_type_column_dropped(db_session):
    cols = db_session.execute(
        text("SELECT column_name FROM information_schema.columns "
             "WHERE table_name='user_tenant_membership'")
    ).scalars().all()
    assert "source_type" not in cols
    assert "work_mode" in cols
