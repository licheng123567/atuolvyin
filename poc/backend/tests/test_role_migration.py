import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models.tenant import UserTenantMembership
from app.models.user import UserAccount


def test_role_check_rejects_legacy_value(db_session, seeded_user, seeded_tenant):
    """非法旧角色值被 role CHECK 约束拒绝(用真实 user/tenant 满足外键,确保命中的是 CHECK)。"""
    bad = UserTenantMembership(
        user_id=seeded_user.id,
        tenant_id=seeded_tenant.id,
        role="provider_admin",  # 旧角色值,已不合法
        is_active=True,
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError) as exc:
        db_session.flush()
    assert "ck_user_tenant_membership_role" in str(exc.value)


def test_work_mode_check_rejects_non_agent_with_work_mode(db_session, seeded_user, seeded_tenant):
    """work_mode 非空但 role 不是 agent → 被 work_mode CHECK 拒绝。"""
    bad = UserTenantMembership(
        user_id=seeded_user.id,
        tenant_id=seeded_tenant.id,
        role="supervisor",
        work_mode="internal",
        is_active=True,
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError) as exc:
        db_session.flush()
    assert "ck_user_tenant_membership_work_mode" in str(exc.value)


def test_work_mode_check_rejects_agent_without_work_mode(db_session, seeded_user, seeded_tenant):
    """role=agent 但 work_mode 为空 → 被 work_mode CHECK 拒绝(双条件另一方向)。"""
    bad = UserTenantMembership(
        user_id=seeded_user.id,
        tenant_id=seeded_tenant.id,
        role="agent",
        work_mode=None,
        is_active=True,
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError) as exc:
        db_session.flush()
    assert "ck_user_tenant_membership_work_mode" in str(exc.value)


def test_platform_role_check_rejects_unknown(db_session):
    """platform_role 非法值被 CHECK 拒绝。"""
    bad = UserAccount(
        phone_enc="test-unknown-platform-role",
        name="x",
        password_hash="x",
        platform_role="god",
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError) as exc:
        db_session.flush()
    assert "ck_user_account_platform_role" in str(exc.value)


def test_valid_new_role_and_work_mode_accepted(db_session, seeded_user, seeded_tenant):
    """合法新角色 + 正确 work_mode 组合应被接受(确认 CHECK 不过度拒绝)。"""
    ok_agent = UserTenantMembership(
        user_id=seeded_user.id,
        tenant_id=seeded_tenant.id,
        role="agent",
        work_mode="external",
        is_active=True,
    )
    db_session.add(ok_agent)
    db_session.flush()  # 不应抛异常
    assert ok_agent.id is not None


def test_source_type_column_dropped(db_session):
    """旧冗余列 source_type 已删除,work_mode 已加。"""
    cols = db_session.execute(
        text("SELECT column_name FROM information_schema.columns "
             "WHERE table_name='user_tenant_membership'")
    ).scalars().all()
    assert "source_type" not in cols
    assert "work_mode" in cols
