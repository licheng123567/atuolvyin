"""§9.3 — SupervisorManager 逐连接电话脱敏单元测试。

SupervisorManager 是纯内存对象，用 FakeWebSocket（记录 send_json 入参的 stub）
即可单测，无需 testcontainers / db_session。
"""
from __future__ import annotations

import pytest

from app.core.crypto import encrypt_phone
from app.risk.supervisor_manager import SupervisorConn, SupervisorManager

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
    await mgr.connect(1, ws, can_see_plaintext=True)

    await mgr.broadcast(1, {"type": "call.started"}, owner_phone_enc=phone_enc)

    assert ws.sent == [{"type": "call.started", "owner_phone_masked": PLAINTEXT_PHONE}]


async def test_broadcast_masked_connection(phone_enc):
    """can_see_plaintext=False 的连接收到脱敏电话。"""
    mgr = SupervisorManager()
    ws = FakeWebSocket()
    await mgr.connect(1, ws, can_see_plaintext=False)

    await mgr.broadcast(1, {"type": "call.started"}, owner_phone_enc=phone_enc)

    assert ws.sent == [{"type": "call.started", "owner_phone_masked": MASKED_PHONE}]


async def test_broadcast_mixed_room(phone_enc):
    """同一房间一个明文连接 + 一个脱敏连接，各自收到对应形式。"""
    mgr = SupervisorManager()
    ws_plain = FakeWebSocket()
    ws_masked = FakeWebSocket()
    await mgr.connect(1, ws_plain, can_see_plaintext=True)
    await mgr.connect(1, ws_masked, can_see_plaintext=False)

    await mgr.broadcast(1, {"type": "call.ended"}, owner_phone_enc=phone_enc)

    assert ws_plain.sent[0]["owner_phone_masked"] == PLAINTEXT_PHONE
    assert ws_masked.sent[0]["owner_phone_masked"] == MASKED_PHONE


async def test_broadcast_no_owner_phone():
    """owner_phone_enc=None 时 payload 原样下发（向后兼容）。"""
    mgr = SupervisorManager()
    ws = FakeWebSocket()
    await mgr.connect(1, ws, can_see_plaintext=False)

    await mgr.broadcast(1, {"type": "ping", "x": 1})

    assert ws.sent == [{"type": "ping", "x": 1}]


async def test_broadcast_event_overwrites_stale_key(phone_enc):
    """event 里塞了假 owner_phone_masked，传 owner_phone_enc 时按连接重算覆盖。"""
    mgr = SupervisorManager()
    ws = FakeWebSocket()
    await mgr.connect(1, ws, can_see_plaintext=False)

    await mgr.broadcast(
        1,
        {"type": "call.started", "owner_phone_masked": "STALE_FAKE_VALUE"},
        owner_phone_enc=phone_enc,
    )

    assert ws.sent[0]["owner_phone_masked"] == MASKED_PHONE


async def test_disconnect_removes_conn(phone_enc):
    """connect 后 disconnect，房间清空，再 broadcast 不报错且 ws 不再收消息。"""
    mgr = SupervisorManager()
    ws = FakeWebSocket()
    await mgr.connect(1, ws, can_see_plaintext=True)
    await mgr.disconnect(1, ws)

    await mgr.broadcast(1, {"type": "call.started"}, owner_phone_enc=phone_enc)

    assert ws.sent == []
    assert mgr._rooms.get(1) is None
