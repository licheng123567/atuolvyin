# poc/backend/tests/ws/test_ws_calls_auth.py
import pytest
from starlette.testclient import TestClient


def _make_call(db_session, seeded_member_user, seeded_tenant, seeded_case):
    from app.models.call import CallRecord
    from app.core.crypto import encrypt_phone
    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000000"),
        initiated_by="pc",
        status="pending_dial",
    )
    db_session.add(call)
    db_session.flush()
    return call


@pytest.fixture
def call_for_member(db_session, seeded_member_user, seeded_tenant, seeded_case):
    return _make_call(db_session, seeded_member_user, seeded_tenant, seeded_case)


def test_ws_rejects_missing_token(db_session, call_for_member):
    from app.main import app
    from app.core.db import get_db

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with pytest.raises(Exception):  # 1008 close raises in TestClient
                with cli.websocket_connect(f"/ws/calls/{call_for_member.id}?role=agent"):
                    pass
    finally:
        app.dependency_overrides.clear()


def test_ws_rejects_invalid_token(db_session, call_for_member):
    from app.main import app
    from app.core.db import get_db

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with pytest.raises(Exception):
                with cli.websocket_connect(
                    f"/ws/calls/{call_for_member.id}?token=garbage&role=agent"
                ):
                    pass
    finally:
        app.dependency_overrides.clear()


def test_ws_rejects_agent_other_user(
    db_session, call_for_member, seeded_supervisor_user, seeded_tenant
):
    from app.main import app
    from app.core.db import get_db
    from app.core.security import create_access_token

    token = create_access_token({
        "sub": str(seeded_supervisor_user.id),
        "user_id": seeded_supervisor_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "supervisor",
        "scope": f"tenant:{seeded_tenant.id}",
    })

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with pytest.raises(Exception):
                with cli.websocket_connect(
                    f"/ws/calls/{call_for_member.id}?token={token}&role=agent"
                ):
                    pass
    finally:
        app.dependency_overrides.clear()


def test_ws_observer_supervisor_accepted(
    db_session, call_for_member, seeded_supervisor_user, seeded_tenant
):
    from app.main import app
    from app.core.db import get_db
    from app.core.security import create_access_token

    token = create_access_token({
        "sub": str(seeded_supervisor_user.id),
        "user_id": seeded_supervisor_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "supervisor",
        "scope": f"tenant:{seeded_tenant.id}",
    })

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with cli.websocket_connect(
                f"/ws/calls/{call_for_member.id}?token={token}&role=observer"
            ) as ws:
                ws.send_json({"type": "ping"})
                msg = ws.receive_json()
                assert msg["type"] == "pong"
    finally:
        app.dependency_overrides.clear()


def test_ws_rejects_cross_tenant_token(db_session, call_for_member, seeded_supervisor_user):
    """A valid JWT for a DIFFERENT tenant must be rejected."""
    from app.main import app
    from app.core.db import get_db
    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token
    from app.models.tenant import Tenant
    from app.models.user import UserAccount

    # Create a separate tenant and a user in it
    other_tenant = Tenant(
        name="别家公司", admin_phone_enc=encrypt_phone("13800000000"),
        plan="trial", is_active=True,
    )
    db_session.add(other_tenant)
    db_session.flush()

    other_user = UserAccount(
        phone_enc=encrypt_phone("13700000000"),
        name="他家催收员",
        password_hash="x",
        is_active=True,
    )
    db_session.add(other_user)
    db_session.flush()

    # Token claims membership in OTHER tenant; supervisor role
    token = create_access_token({
        "sub": str(other_user.id),
        "user_id": other_user.id,
        "tenant_id": other_tenant.id,  # ← different tenant from call_for_member.tenant_id
        "role": "supervisor",
        "scope": f"tenant:{other_tenant.id}",
    })

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with pytest.raises(Exception):
                with cli.websocket_connect(
                    f"/ws/calls/{call_for_member.id}?token={token}&role=observer"
                ):
                    pass
    finally:
        app.dependency_overrides.clear()
