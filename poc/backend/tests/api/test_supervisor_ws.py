import os
import pytest
from starlette.testclient import TestClient

os.environ.setdefault("RISK_ANALYZER_BACKEND", "mock")


@pytest.fixture(autouse=True)
def _reset_supervisor_manager():
    """每条测试前后清空 SupervisorManager 单例，避免房间状态串台。"""
    import app.risk.supervisor_manager as sm
    sm._supervisor_manager = None
    yield
    sm._supervisor_manager = None


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


def _provider_supervisor_token(db_session, seeded_tenant, *, with_active_contract: bool = False):
    """造一个服务商侧督导（membership.provider_id 非空），返回 (user, token)。

    with_active_contract=True 时额外建一条有效 ProviderTenantContract。
    """
    from datetime import UTC, datetime

    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import (
        ProviderTenantContract,
        ServiceProvider,
        UserTenantMembership,
    )
    from app.models.user import UserAccount

    provider = ServiceProvider(
        name="测试服务商",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13900000000"),
    )
    db_session.add(provider)
    db_session.flush()

    user = UserAccount(
        name="服务商督导",
        phone_enc=encrypt_phone("13911112222"),
        password_hash=get_password_hash("pw"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    mem = UserTenantMembership(
        tenant_id=seeded_tenant.id,
        user_id=user.id,
        role="supervisor",
        provider_id=provider.id,
        is_active=True,
    )
    db_session.add(mem)
    db_session.flush()

    if with_active_contract:
        contract = ProviderTenantContract(
            tenant_id=seeded_tenant.id,
            provider_id=provider.id,
            signed_at=datetime.now(UTC),
            service_types=["collection"],
            status="active",
            expires_at=None,
        )
        db_session.add(contract)
        db_session.flush()

    token = create_access_token({
        "sub": str(user.id),
        "user_id": user.id,
        "tenant_id": seeded_tenant.id,
        "role": "supervisor",
        "provider_id": provider.id,
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return user, token


def test_property_supervisor_snapshot_sees_plaintext(db_session, seeded_tenant):
    """物业内部督导（provider_id 缺省/None）握手后连接快照 can_see_plaintext=True。"""
    from app.main import app
    from app.core.db import get_db
    from app.risk.supervisor_manager import get_supervisor_manager

    def override_db():
        yield db_session

    _, token = _supervisor_token(db_session, seeded_tenant)
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with cli.websocket_connect(f"/ws/supervisor?token={token}"):
                room = get_supervisor_manager()._rooms.get(seeded_tenant.id)
                assert room is not None and len(room) == 1
                conn = next(iter(room.values()))
                assert conn.can_see_plaintext is True
    finally:
        app.dependency_overrides.clear()


def test_provider_supervisor_no_contract_snapshot_is_masked(db_session, seeded_tenant):
    """服务商侧督导、无有效合同 → 握手快照 can_see_plaintext=False。"""
    from app.main import app
    from app.core.db import get_db
    from app.risk.supervisor_manager import get_supervisor_manager

    def override_db():
        yield db_session

    _, token = _provider_supervisor_token(db_session, seeded_tenant)
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with cli.websocket_connect(f"/ws/supervisor?token={token}"):
                room = get_supervisor_manager()._rooms.get(seeded_tenant.id)
                assert room is not None and len(room) == 1
                conn = next(iter(room.values()))
                assert conn.can_see_plaintext is False
    finally:
        app.dependency_overrides.clear()


def test_provider_supervisor_active_contract_sees_plaintext(db_session, seeded_tenant):
    """服务商侧督导、有有效合同 → 握手快照 can_see_plaintext=True。"""
    from app.main import app
    from app.core.db import get_db
    from app.risk.supervisor_manager import get_supervisor_manager

    def override_db():
        yield db_session

    _, token = _provider_supervisor_token(
        db_session, seeded_tenant, with_active_contract=True
    )
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with cli.websocket_connect(f"/ws/supervisor?token={token}"):
                room = get_supervisor_manager()._rooms.get(seeded_tenant.id)
                assert room is not None and len(room) == 1
                conn = next(iter(room.values()))
                assert conn.can_see_plaintext is True
    finally:
        app.dependency_overrides.clear()
