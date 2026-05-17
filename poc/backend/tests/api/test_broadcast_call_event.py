"""§9.3 — _broadcast_call_event 调用方契约测试。

验证调用方把业主电话密文交给 SupervisorManager.broadcast 处理，
自己不再硬编码 owner_phone_masked。逐连接脱敏逻辑本身由
tests/risk/test_supervisor_manager.py 覆盖。
"""
from __future__ import annotations

import pytest

from app.core.crypto import encrypt_phone


class _FakeManager:
    """记录 broadcast 入参的假 SupervisorManager。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def broadcast(self, tenant_id, event, *, owner_phone_enc=None) -> None:
        self.calls.append(
            {"tenant_id": tenant_id, "event": event, "owner_phone_enc": owner_phone_enc}
        )


@pytest.fixture
def fake_supervisor_manager(monkeypatch):
    fake = _FakeManager()
    import app.risk.supervisor_manager as sm
    monkeypatch.setattr(sm, "_supervisor_manager", fake)
    return fake


async def test_broadcast_call_event_passes_owner_phone_enc(
    db_session, seeded_tenant, seeded_case, seeded_owner, seeded_member_user,
    fake_supervisor_manager,
):
    """_broadcast_call_event 把 owner.phone_enc 交给 broadcast，payload 不含 owner_phone_masked。"""
    from app.api.calls_v1 import _broadcast_call_event
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000000"),
        initiated_by="pc",
        status="dialing",
    )
    db_session.add(call)
    db_session.flush()

    await _broadcast_call_event(db_session, call, "call.started")

    assert len(fake_supervisor_manager.calls) == 1
    sent = fake_supervisor_manager.calls[0]
    assert sent["tenant_id"] == seeded_tenant.id
    # 业主电话以密文形式交给 broadcast，由其逐连接脱敏
    assert sent["owner_phone_enc"] == seeded_owner.phone_enc
    # 调用方自己不再拼 owner_phone_masked
    assert "owner_phone_masked" not in sent["event"]
    assert sent["event"]["type"] == "call.started"
    assert sent["event"]["case_id"] == seeded_case.id
