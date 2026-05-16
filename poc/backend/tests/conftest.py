import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

os.environ["ASR_BACKEND"] = "mock"
os.environ["LLM_BACKEND"] = "mock"
os.environ["LOCAL_STORAGE_ROOT"] = "/tmp/autoluyin_test_recordings"
os.environ["AUTOLUYIN_AES_KEY"] = "deadbeef" * 8  # 64 hex chars — test key only
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"

from app.main import app  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.core.crypto import encrypt_phone  # noqa: E402
from app.models.base import Base  # noqa: E402


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def engine(pg_container):
    url = pg_container.get_connection_url().replace("psycopg2", "psycopg")
    eng = create_engine(url, future=True)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine):
    # Outer connection + transaction: session.commit() hits SAVEPOINT, not real commit.
    # trans.rollback() at teardown erases all test data regardless of session commits.
    connection = engine.connect()
    trans = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    try:
        trans.rollback()  # may already be rolled back if test raised IntegrityError
    except Exception:
        pass
    connection.close()


@pytest.fixture
async def client(db_session):
    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


from app.core.security import get_password_hash  # noqa: E402
from app.models.user import UserAccount  # noqa: E402


@pytest.fixture
def seeded_user(db_session):
    user = UserAccount(
        phone_enc=encrypt_phone("13800138001"),
        name="测试用户",
        password_hash=get_password_hash("Test@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


from app.models.tenant import Tenant, UserTenantMembership  # noqa: E402


@pytest.fixture
def seeded_tenant(db_session):
    tenant = Tenant(
        name="测试物业公司",
        admin_phone_enc=encrypt_phone("13900139001"),
        plan="trial",
        is_active=True,
    )
    db_session.add(tenant)
    db_session.flush()
    return tenant


@pytest.fixture
def ops_auth_headers(seeded_user):
    from app.core.security import create_access_token
    token = create_access_token({
        "sub": str(seeded_user.id),
        "user_id": seeded_user.id,
        "tenant_id": None,
        "role": "ops",
        "scope": "platform",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def super_auth_headers(seeded_user):
    from app.core.security import create_access_token
    token = create_access_token({
        "sub": str(seeded_user.id),
        "user_id": seeded_user.id,
        "tenant_id": None,
        "role": "superadmin",
        "scope": "platform",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def superadmin_auth_headers(seeded_user):
    from app.core.security import create_access_token
    token = create_access_token({
        "sub": str(seeded_user.id),
        "user_id": seeded_user.id,
        "tenant_id": None,
        "role": "superadmin",
        "scope": "platform",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seeded_audit_log(db_session, seeded_user, seeded_tenant):
    from app.models.audit import AuditLog
    log = AuditLog(
        actor_user_id=seeded_user.id,
        actor_role="superadmin",
        tenant_id=seeded_tenant.id,
        action="tenant.create",
        target_type="tenant",
        target_id=seeded_tenant.id,
        payload={"name": "测试物业公司", "plan": "trial"},
    )
    db_session.add(log)
    db_session.flush()
    return log


@pytest.fixture
def seeded_plan_config(db_session):
    from app.models.audit import PlanConfig
    plans = [
        PlanConfig(
            plan_name="trial",
            display_name="试用版",
            monthly_minutes=60,
            price_monthly=0,
            features={"realtime_assist": False},
            is_active=True,
        ),
        PlanConfig(
            plan_name="basic",
            display_name="基础版",
            monthly_minutes=500,
            price_monthly=99,
            features={"script_library": True},
            is_active=True,
        ),
    ]
    for p in plans:
        db_session.add(p)
    db_session.flush()
    return plans


@pytest.fixture
def seeded_member_user(db_session, seeded_tenant):
    from app.core.security import get_password_hash
    user = UserAccount(
        phone_enc=encrypt_phone("13811138111"),
        name="催收员小王",
        password_hash=get_password_hash("Agent@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    membership = UserTenantMembership(
        user_id=user.id,
        tenant_id=seeded_tenant.id,
        role="agent",
        work_mode="internal",
        is_active=True,
    )
    db_session.add(membership)
    db_session.flush()
    return user


@pytest.fixture
def admin_auth_headers(seeded_user, seeded_tenant, db_session):
    from app.core.security import create_access_token
    membership = UserTenantMembership(
        user_id=seeded_user.id,
        tenant_id=seeded_tenant.id,
        role="admin",
        is_active=True,
    )
    db_session.add(membership)
    db_session.flush()
    token = create_access_token({
        "sub": str(seeded_user.id),
        "user_id": seeded_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "admin",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}


from decimal import Decimal  # noqa: E402


@pytest.fixture
def seeded_owner(db_session, seeded_tenant):
    from app.models.case import OwnerProfile
    owner = OwnerProfile(
        tenant_id=seeded_tenant.id,
        name="张三",
        phone_enc=encrypt_phone("13712345678"),
        building="1栋",
        room="101",
    )
    db_session.add(owner)
    db_session.flush()
    return owner


@pytest.fixture
def seeded_case(db_session, seeded_tenant, seeded_owner):
    from app.models.case import CollectionCase
    case = CollectionCase(
        tenant_id=seeded_tenant.id,
        owner_id=seeded_owner.id,
        pool_type="public",
        stage="new",
        amount_owed=Decimal("3000.00"),
        months_overdue=3,
        priority_score=1200,
    )
    db_session.add(case)
    db_session.flush()
    return case


@pytest.fixture
def seeded_supervisor_user(db_session, seeded_tenant):
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    user = UserAccount(
        phone_enc=encrypt_phone("13922239222"),
        name="督导李四",
        password_hash=get_password_hash("Supervisor@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    membership = UserTenantMembership(
        user_id=user.id,
        tenant_id=seeded_tenant.id,
        role="supervisor",
        is_active=True,
    )
    db_session.add(membership)
    db_session.flush()
    return user


@pytest.fixture
def agent_auth_headers(seeded_member_user, seeded_tenant):
    from app.core.security import create_access_token
    token = create_access_token({
        "sub": str(seeded_member_user.id),
        "user_id": seeded_member_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "agent",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def supervisor_auth_headers(seeded_supervisor_user, seeded_tenant):
    from app.core.security import create_access_token
    token = create_access_token({
        "sub": str(seeded_supervisor_user.id),
        "user_id": seeded_supervisor_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "supervisor",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def reset_mipush_mock():
    from app.services import mipush
    mipush._reset_for_tests()
    yield
    mipush._reset_for_tests()


@pytest.fixture
def seeded_device_with_push_reg(db_session, seeded_member_user, seeded_tenant):
    from app.models.device import DeviceProfile
    device = DeviceProfile(
        device_id="test-device-001",
        user_id=seeded_member_user.id,
        tenant_id=seeded_tenant.id,
        brand="Xiaomi",
        model="Redmi K70",
        os_version="MIUI 14",
        push_reg_id="reg-id-xiaomi-abc123",
        push_provider="xiaomi",
        is_healthy=True,
    )
    db_session.add(device)
    db_session.flush()
    return device


@pytest.fixture
def seeded_assigned_case(db_session, seeded_case, seeded_member_user):
    seeded_case.assigned_to = seeded_member_user.id
    db_session.flush()
    return seeded_case
