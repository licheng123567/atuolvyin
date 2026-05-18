"""§9.3 — SupervisorManager 逐连接电话脱敏单元测试。

SupervisorManager 是纯内存对象，用 FakeWebSocket（记录 send_json 入参的 stub）
即可单测，无需 testcontainers / db_session。
"""
from __future__ import annotations

import pytest

from app.core.crypto import encrypt_phone
from app.risk.supervisor_manager import SupervisorManager

PLAINTEXT_PHONE = "13800001234"
MASKED_PHONE = "138****1234"


class FakeWebSocket:
    """最小 stub，匹配 SupervisorManager 用到的 WebSocket.send_json 接口。"""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)


@pytest.fixture
def phone_enc() -> str:
    return encrypt_phone(PLAINTEXT_PHONE)


async def test_broadcast_plaintext_connection(phone_enc):
    """can_see_plaintext=True 的连接收到 11 位明文电话。"""
    mgr = SupervisorManager()
    ws = FakeWebSocket()
    await mgr.connect(1, ws, can_see_plaintext=True, provider_id=None)

    await mgr.broadcast(1, {"type": "call.started"}, owner_phone_enc=phone_enc, call_provider_id=None)

    assert ws.sent == [{"type": "call.started", "owner_phone_masked": PLAINTEXT_PHONE}]


async def test_broadcast_masked_connection(phone_enc):
    """can_see_plaintext=False 的连接收到脱敏电话。"""
    mgr = SupervisorManager()
    ws = FakeWebSocket()
    await mgr.connect(1, ws, can_see_plaintext=False, provider_id=None)

    await mgr.broadcast(1, {"type": "call.started"}, owner_phone_enc=phone_enc, call_provider_id=None)

    assert ws.sent == [{"type": "call.started", "owner_phone_masked": MASKED_PHONE}]


async def test_broadcast_mixed_room(phone_enc):
    """同一房间一个明文连接 + 一个脱敏连接，各自收到对应形式。"""
    mgr = SupervisorManager()
    ws_plain = FakeWebSocket()
    ws_masked = FakeWebSocket()
    await mgr.connect(1, ws_plain, can_see_plaintext=True, provider_id=None)
    await mgr.connect(1, ws_masked, can_see_plaintext=False, provider_id=None)

    await mgr.broadcast(1, {"type": "call.ended"}, owner_phone_enc=phone_enc, call_provider_id=None)

    assert ws_plain.sent[0]["owner_phone_masked"] == PLAINTEXT_PHONE
    assert ws_masked.sent[0]["owner_phone_masked"] == MASKED_PHONE


async def test_broadcast_no_owner_phone():
    """owner_phone_enc=None 时 payload 原样下发（向后兼容）。"""
    mgr = SupervisorManager()
    ws = FakeWebSocket()
    await mgr.connect(1, ws, can_see_plaintext=False, provider_id=None)

    await mgr.broadcast(1, {"type": "ping", "x": 1}, call_provider_id=None)

    assert ws.sent == [{"type": "ping", "x": 1}]


async def test_broadcast_event_overwrites_stale_key(phone_enc):
    """event 里塞了假 owner_phone_masked，传 owner_phone_enc 时按连接重算覆盖。"""
    mgr = SupervisorManager()
    ws = FakeWebSocket()
    await mgr.connect(1, ws, can_see_plaintext=False, provider_id=None)

    await mgr.broadcast(
        1,
        {"type": "call.started", "owner_phone_masked": "STALE_FAKE_VALUE"},
        owner_phone_enc=phone_enc,
        call_provider_id=None,
    )

    assert ws.sent[0]["owner_phone_masked"] == MASKED_PHONE


async def test_disconnect_removes_conn(phone_enc):
    """connect 后 disconnect，房间清空，再 broadcast 不报错且 ws 不再收消息。"""
    mgr = SupervisorManager()
    ws = FakeWebSocket()
    await mgr.connect(1, ws, can_see_plaintext=True, provider_id=None)
    await mgr.disconnect(1, ws)

    await mgr.broadcast(1, {"type": "call.started"}, owner_phone_enc=phone_enc, call_provider_id=None)

    assert ws.sent == []
    assert mgr._rooms.get(1) is None


async def test_broadcast_isolated_by_tenant(phone_enc):
    """broadcast 到 tenant 1 不会泄漏给注册在 tenant 2 的连接。"""
    mgr = SupervisorManager()
    ws_t1 = FakeWebSocket()
    ws_t2 = FakeWebSocket()
    await mgr.connect(1, ws_t1, can_see_plaintext=True, provider_id=None)
    await mgr.connect(2, ws_t2, can_see_plaintext=True, provider_id=None)

    await mgr.broadcast(1, {"type": "call.started"}, owner_phone_enc=phone_enc, call_provider_id=None)

    assert len(ws_t1.sent) == 1
    assert ws_t2.sent == []


async def test_broadcast_drops_failed_connection(phone_enc):
    """某连接 send_json 抛错时，broadcast 继续投递其余连接并把坏连接移出房间。"""

    class RaisingWebSocket:
        async def send_json(self, data: dict) -> None:
            raise RuntimeError("socket dead")

    mgr = SupervisorManager()
    bad_ws = RaisingWebSocket()
    good_ws = FakeWebSocket()
    await mgr.connect(1, bad_ws, can_see_plaintext=True, provider_id=None)
    await mgr.connect(1, good_ws, can_see_plaintext=True, provider_id=None)

    await mgr.broadcast(1, {"type": "call.started"}, owner_phone_enc=phone_enc, call_provider_id=None)

    # 坏连接抛错不影响健康连接收消息
    assert len(good_ws.sent) == 1
    # 坏连接被移出房间，健康连接仍在
    assert bad_ws not in mgr._rooms[1]
    assert good_ws in mgr._rooms[1]


# ---------------------------------------------------------------------------
# Task 4 — provider scope 过滤测试
# ---------------------------------------------------------------------------

PROVIDER_A_ID = 10
PROVIDER_B_ID = 20
TENANT_ID = 1


async def test_broadcast_provider_scope_only_provider_a_receives():
    """broadcast(call_provider_id=A) → 只有 provider A 连接收到；物业和 B 不收。"""
    mgr = SupervisorManager()
    ws_property = FakeWebSocket()
    ws_a = FakeWebSocket()
    ws_b = FakeWebSocket()

    await mgr.connect(TENANT_ID, ws_property, can_see_plaintext=True, provider_id=None)
    await mgr.connect(TENANT_ID, ws_a, can_see_plaintext=True, provider_id=PROVIDER_A_ID)
    await mgr.connect(TENANT_ID, ws_b, can_see_plaintext=True, provider_id=PROVIDER_B_ID)

    event = {"type": "call.started", "call_id": 1}
    await mgr.broadcast(TENANT_ID, event, call_provider_id=PROVIDER_A_ID)

    assert len(ws_a.sent) == 1
    assert ws_property.sent == []
    assert ws_b.sent == []


async def test_broadcast_provider_scope_none_only_property_receives():
    """broadcast(call_provider_id=None) → 只有物业督导连接收到；服务商 A/B 不收。"""
    mgr = SupervisorManager()
    ws_property = FakeWebSocket()
    ws_a = FakeWebSocket()
    ws_b = FakeWebSocket()

    await mgr.connect(TENANT_ID, ws_property, can_see_plaintext=True, provider_id=None)
    await mgr.connect(TENANT_ID, ws_a, can_see_plaintext=False, provider_id=PROVIDER_A_ID)
    await mgr.connect(TENANT_ID, ws_b, can_see_plaintext=False, provider_id=PROVIDER_B_ID)

    event = {"type": "call.started", "call_id": 2}
    await mgr.broadcast(TENANT_ID, event, call_provider_id=None)

    assert len(ws_property.sent) == 1
    assert ws_a.sent == []
    assert ws_b.sent == []


async def test_broadcast_provider_scope_only_provider_b_receives():
    """broadcast(call_provider_id=B) → 只有 provider B 收到；物业和 A 不收。"""
    mgr = SupervisorManager()
    ws_property = FakeWebSocket()
    ws_a = FakeWebSocket()
    ws_b = FakeWebSocket()

    await mgr.connect(TENANT_ID, ws_property, can_see_plaintext=True, provider_id=None)
    await mgr.connect(TENANT_ID, ws_a, can_see_plaintext=True, provider_id=PROVIDER_A_ID)
    await mgr.connect(TENANT_ID, ws_b, can_see_plaintext=True, provider_id=PROVIDER_B_ID)

    event = {"type": "call.alert", "call_id": 3}
    await mgr.broadcast(TENANT_ID, event, call_provider_id=PROVIDER_B_ID)

    assert len(ws_b.sent) == 1
    assert ws_property.sent == []
    assert ws_a.sent == []


async def test_broadcast_provider_scope_with_phone_enc(phone_enc):
    """scope 过滤 + phone 脱敏同时生效：A 连接收到脱敏电话，物业和 B 不收。"""
    mgr = SupervisorManager()
    ws_property = FakeWebSocket()
    ws_a = FakeWebSocket()
    ws_b = FakeWebSocket()

    await mgr.connect(TENANT_ID, ws_property, can_see_plaintext=True, provider_id=None)
    await mgr.connect(TENANT_ID, ws_a, can_see_plaintext=False, provider_id=PROVIDER_A_ID)
    await mgr.connect(TENANT_ID, ws_b, can_see_plaintext=True, provider_id=PROVIDER_B_ID)

    event = {"type": "call.started", "call_id": 4}
    await mgr.broadcast(
        TENANT_ID, event, owner_phone_enc=phone_enc, call_provider_id=PROVIDER_A_ID
    )

    assert len(ws_a.sent) == 1
    assert ws_a.sent[0]["owner_phone_masked"] == MASKED_PHONE
    assert ws_property.sent == []
    assert ws_b.sent == []
