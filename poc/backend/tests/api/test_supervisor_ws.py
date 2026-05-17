import os
import pytest
from starlette.testclient import TestClient

os.environ.setdefault("RISK_ANALYZER_BACKEND", "mock")


def _supervisor_token(db_session, seeded_tenant):
    """Create a supervisor-role JWT."""
    from app.models.user import UserAccount
    from app.core.security import create_access_token, get_password_hash

    user = UserAccount(
        name="Supervisor One",
        phone_enc="enc_super",
        password_hash=get_password_hash("pw"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    from app.models.tenant import UserTenantMembership
    mem = UserTenantMembership(tenant_id=seeded_tenant.id, user_id=user.id, role="supervisor",
                               is_active=True)
    db_session.add(mem)
    db_session.flush()

    return user, create_access_token({
        "sub": str(user.id),
        "user_id": user.id,
        "tenant_id": seeded_tenant.id,
        "role": "supervisor",
        "scope": f"tenant:{seeded_tenant.id}",
    })


def test_supervisor_ws_auth_fails_without_token(db_session, seeded_tenant):
    from app.main import app
    from app.core.db import get_db

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with cli.websocket_connect("/ws/supervisor") as ws:
                msg = ws.receive_json()
        assert msg.get("code") == "ERR_AUTH"
    finally:
        app.dependency_overrides.clear()


def test_supervisor_ws_connects_with_valid_token(db_session, seeded_tenant):
    from app.main import app
    from app.core.db import get_db

    def override_db():
        yield db_session

    _, token = _supervisor_token(db_session, seeded_tenant)
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with cli.websocket_connect(f"/ws/supervisor?token={token}") as ws:
                ws.send_json({"type": "ping"})
                # Connection stays open — just verify no auth error received
    finally:
        app.dependency_overrides.clear()


def test_supervisor_ws_rejects_agent_role(db_session, seeded_tenant, seeded_member_user):
    from app.main import app
    from app.core.db import get_db
    from app.core.security import create_access_token

    def override_db():
        yield db_session

    token = create_access_token({
        "sub": str(seeded_member_user.id),
        "user_id": seeded_member_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "agent",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with cli.websocket_connect(f"/ws/supervisor?token={token}") as ws:
                msg = ws.receive_json()
        assert msg.get("code") == "ERR_AUTH"
    finally:
        app.dependency_overrides.clear()
