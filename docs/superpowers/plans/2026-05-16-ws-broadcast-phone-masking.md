# §9.3 WS 广播逐订阅者电话脱敏 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让实时通话墙 WS 广播按每个订阅连接的身份分别下发明文 / 脱敏业主电话，修复服务商督导无条件收到明文业主电话的过度披露缺口。

**Architecture:** WS 群发无法在「发送时」知道订阅者身份 —— 所以在 WS 握手时把「该连接能否看明文」算成一个布尔快照（`SupervisorConn.can_see_plaintext`）存进连接对象；`SupervisorManager.broadcast` 收到密文 `owner_phone_enc` 时，按每个连接的布尔逐一注入 `owner_phone_masked`。调用方不再硬编码 `provider_id=None`。

**Tech Stack:** Python 3.12 + FastAPI WebSocket + SQLAlchemy 2.0 + pytest（`asyncio_mode = "auto"`，`async def test_` 直接生效）+ starlette `TestClient`。

**设计文档：** `docs/superpowers/specs/2026-05-16-ws-broadcast-phone-masking-design.md`

**前置事实（实现者必读）：**
- 仓库根 `/Users/shuo/AI/autoluyin`，后端在 `poc/backend/`，所有 `pytest` 命令在 `poc/backend/` 目录下执行。
- 测试用 `python3.12 -m pytest`（testcontainers 需宿主 docker daemon；从宿主跑，不在容器内跑）。
- `pytest` 配置 `asyncio_mode = "auto"` —— `async def test_xxx` 无需 `@pytest.mark.asyncio` 装饰器。
- `app.core.phone_visibility` 已有 `is_provider_contract_active(db, tenant_id, provider_id) -> bool`、`should_reveal_owner_phone(*, role, provider_id, contract_active, project_active, legal_case_stage) -> bool`、`display_owner_phone(cipher, *, reveal) -> str | None`，本计划复用，不改它们。
- `app.core.crypto.encrypt_phone(plain) -> str` / `mask_phone(cipher) -> str`：`mask_phone` 对 11 位号码返回 `前3位 + "****" + 后4位`，即 `13800001234` → `138****1234`。

---

## File Structure

| 文件 | 职责 | 操作 |
|------|------|------|
| `poc/backend/app/risk/supervisor_manager.py` | WS 连接池：房间结构 + 连接身份快照 + 逐连接广播 | 改 |
| `poc/backend/app/api/ws_supervisor.py` | `/ws/supervisor` 端点：握手时算 `can_see_plaintext` 快照 | 改 |
| `poc/backend/app/api/calls_v1.py` | `_broadcast_call_event`：调用方传密文、删硬编码 reveal | 改 |
| `poc/backend/tests/risk/test_supervisor_manager.py` | `SupervisorManager` 单元测试（6 条） | 建 |
| `poc/backend/tests/api/test_supervisor_ws.py` | `ws_supervisor` 握手快照集成测试（补 2 条） | 改 |
| `poc/backend/tests/api/test_broadcast_call_event.py` | `_broadcast_call_event` 调用方契约测试（1 条） | 建 |
| `docs/superpowers/specs/2026-05-16-role-model-refactor-design.md` | §9.3 标注「已实现」 | 改 |

无 DB 迁移、无 Pydantic schema 变更、无前端 / Android 改动。

---

## Task 1: `SupervisorConn` + `SupervisorManager` 逐连接广播

**Files:**
- Modify: `poc/backend/app/risk/supervisor_manager.py`（整文件重写，当前 48 行）
- Test: `poc/backend/tests/risk/test_supervisor_manager.py`（新建）

`tests/risk/` 目录已存在且含 `__init__.py`，无需新建目录。

- [ ] **Step 1: 写失败测试**

新建 `poc/backend/tests/risk/test_supervisor_manager.py`，完整内容：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/risk/test_supervisor_manager.py -v`
Expected: FAIL —— `ImportError: cannot import name 'SupervisorConn'`（`connect` 还不接 `can_see_plaintext`、`broadcast` 还不接 `owner_phone_enc`）。

- [ ] **Step 3: 重写 `supervisor_manager.py`**

把 `poc/backend/app/risk/supervisor_manager.py` 整文件替换为：

```python
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass

from fastapi import WebSocket

from app.core.phone_visibility import display_owner_phone

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SupervisorConn:
    """单个 supervisor WS 连接的身份快照。WS 握手时算一次，连接生命周期内不变。"""

    can_see_plaintext: bool


class SupervisorManager:
    """In-process WebSocket pool for supervisor clients, keyed by tenant_id.

    §9.3 —— 每个连接在握手时算出 can_see_plaintext 快照存进 SupervisorConn；
    broadcast 收到 owner_phone_enc 密文时，按每个连接的快照逐一注入
    owner_phone_masked（明文 / 脱敏）。
    """

    def __init__(self) -> None:
        self._rooms: dict[int, dict[WebSocket, SupervisorConn]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def connect(
        self, tenant_id: int, ws: WebSocket, *, can_see_plaintext: bool
    ) -> None:
        async with self._lock:
            self._rooms[tenant_id][ws] = SupervisorConn(can_see_plaintext=can_see_plaintext)

    async def disconnect(self, tenant_id: int, ws: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(tenant_id)
            if room is not None:
                room.pop(ws, None)
                if not room:
                    self._rooms.pop(tenant_id, None)

    async def broadcast(
        self,
        tenant_id: int,
        event: dict,
        *,
        owner_phone_enc: str | None = None,
    ) -> None:
        """向 tenant 房间群发 event。

        owner_phone_enc 非空时，按每个连接的 can_see_plaintext 快照逐一注入
        owner_phone_masked（覆盖 event 里同名键）；为空时 event 原样下发。
        """
        async with self._lock:
            members = list(self._rooms.get(tenant_id, {}).items())
        for ws, conn in members:
            try:
                if owner_phone_enc is not None:
                    payload = {
                        **event,
                        "owner_phone_masked": display_owner_phone(
                            owner_phone_enc, reveal=conn.can_see_plaintext
                        ),
                    }
                else:
                    payload = event
                await ws.send_json(payload)
            except Exception as exc:
                logger.warning("supervisor broadcast failed tenant=%s: %s", tenant_id, exc)
                await self.disconnect(tenant_id, ws)


_supervisor_manager: SupervisorManager | None = None


def get_supervisor_manager() -> SupervisorManager:
    global _supervisor_manager
    if _supervisor_manager is None:
        _supervisor_manager = SupervisorManager()
    return _supervisor_manager
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/risk/test_supervisor_manager.py -v`
Expected: PASS —— 6 passed。

- [ ] **Step 5: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/risk/supervisor_manager.py poc/backend/tests/risk/test_supervisor_manager.py
git commit -m "feat(v2.2): §9.3 SupervisorManager 逐连接电话脱敏 + 连接身份快照"
```

---

## Task 2: `ws_supervisor` 握手时算 `can_see_plaintext` 快照

**Files:**
- Modify: `poc/backend/app/api/ws_supervisor.py`（整文件重写，当前 66 行）
- Test: `poc/backend/tests/api/test_supervisor_ws.py`（在已有文件末尾追加 2 条 + 文件头 1 个 autouse fixture）

- [ ] **Step 1: 写失败测试**

在 `poc/backend/tests/api/test_supervisor_ws.py` **文件头**（`os.environ.setdefault(...)` 行之后）插入一个重置 manager 单例的 autouse fixture：

```python
@pytest.fixture(autouse=True)
def _reset_supervisor_manager():
    """每条测试前后清空 SupervisorManager 单例，避免房间状态串台。"""
    import app.risk.supervisor_manager as sm
    sm._supervisor_manager = None
    yield
    sm._supervisor_manager = None
```

在**文件末尾**追加两条测试：

```python
def _provider_supervisor_token(db_session, seeded_tenant):
    """造一个服务商侧督导（membership.provider_id 非空、无有效合同），返回 (user, token)。"""
    from app.core.crypto import encrypt_phone
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import ServiceProvider, UserTenantMembership
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
```

> 说明：`_supervisor_token` 已在该文件顶部定义（造物业内部督导，membership 无 `provider_id`）。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_supervisor_ws.py -v`
Expected: FAIL —— 新增 2 条因 `SupervisorManager.connect()` 缺 `can_see_plaintext` 关键字参数报 `TypeError`（`ws_supervisor` 还在用旧的 `manager.connect(tenant_id, websocket)`）。

- [ ] **Step 3: 重写 `ws_supervisor.py`**

把 `poc/backend/app/api/ws_supervisor.py` 整文件替换为：

```python
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.phone_visibility import is_provider_contract_active, should_reveal_owner_phone
from app.risk.supervisor_manager import get_supervisor_manager
from app.ws.auth import decode_ws_token

router = APIRouter()
logger = logging.getLogger(__name__)

_SUPERVISOR_ROLES = {
    "supervisor",
    "admin",
    "project_manager",
}  # Sprint 14.2 — 实时通话墙观察者


@router.websocket("/ws/supervisor")
async def ws_supervisor(
    websocket: WebSocket,
    token: Annotated[str | None, Query()] = None,
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
):
    payload = decode_ws_token(token or "")
    if payload is None:
        await websocket.accept()
        await websocket.send_json({"type": "error", "code": "ERR_AUTH", "message": "invalid token"})
        await websocket.close(code=1008)
        return

    role = payload.get("role", "")
    if role not in _SUPERVISOR_ROLES:
        await websocket.accept()
        await websocket.send_json(
            {"type": "error", "code": "ERR_AUTH", "message": "insufficient role"}
        )
        await websocket.close(code=1008)
        return

    tenant_id = int(payload.get("tenant_id") or 0)
    if not tenant_id:
        await websocket.accept()
        await websocket.send_json(
            {"type": "error", "code": "ERR_AUTH", "message": "missing tenant"}
        )
        await websocket.close(code=1008)
        return

    # §9.3 —— 握手时算「该连接能否看明文业主电话」快照。
    # provider_id 为 None = 物业内部，永远明文；非空 = 服务商侧，按合同有效性快照决定。
    # 权衡（见设计文档 §4）：合同有效性只在连接时查一次；中途解约的脱敏延迟到下次重连。
    provider_id = payload.get("provider_id")
    if provider_id is None:
        can_see_plaintext = True
    else:
        contract_active = is_provider_contract_active(db, tenant_id, provider_id)
        can_see_plaintext = should_reveal_owner_phone(
            role=role,
            provider_id=provider_id,
            contract_active=contract_active,
            project_active=True,  # 广播事件不绑单个项目语境，固定 True
        )

    await websocket.accept()
    manager = get_supervisor_manager()
    await manager.connect(tenant_id, websocket, can_see_plaintext=can_see_plaintext)
    logger.info(
        "supervisor connected tenant=%s role=%s plaintext=%s",
        tenant_id,
        role,
        can_see_plaintext,
    )

    try:
        while True:
            data = await websocket.receive_text()
            if data == '{"type":"ping"}':
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(tenant_id, websocket)
        logger.info("supervisor disconnected tenant=%s", tenant_id)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_supervisor_ws.py -v`
Expected: PASS —— 5 passed（原 3 条 + 新增 2 条）。

- [ ] **Step 5: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/api/ws_supervisor.py poc/backend/tests/api/test_supervisor_ws.py
git commit -m "feat(v2.2): §9.3 ws_supervisor 握手时快照连接电话可见性"
```

---

## Task 3: `_broadcast_call_event` 调用方传密文、删硬编码 reveal

**Files:**
- Modify: `poc/backend/app/api/calls_v1.py:291-319`（`_broadcast_call_event` 函数）
- Test: `poc/backend/tests/api/test_broadcast_call_event.py`（新建）

> 注意：`calls_v1.py` 第 21-25 行 `from app.core.phone_visibility import (...)` 的 `should_reveal_owner_phone` / `display_owner_phone` 在第 137-143、827-923 行仍被列表 / 详情端点使用 —— **import 块保持不变**，本任务只删 `_broadcast_call_event` 内部第 302 行那一处用法。

- [ ] **Step 1: 写失败测试**

新建 `poc/backend/tests/api/test_broadcast_call_event.py`，完整内容：

```python
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
```

> `seeded_case` fixture 依赖 `seeded_owner`，二者 `owner_id` 已关联（见 `tests/conftest.py`）。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_broadcast_call_event.py -v`
Expected: FAIL —— `assert "owner_phone_masked" not in sent["event"]` 失败（当前 `_broadcast_call_event` 仍把 `owner_phone_masked` 塞进 payload），且 `sent["owner_phone_enc"]` 为 `None`。

- [ ] **Step 3: 改写 `_broadcast_call_event`**

把 `poc/backend/app/api/calls_v1.py` 第 291-319 行整个 `_broadcast_call_event` 函数替换为：

```python
async def _broadcast_call_event(db: Session, call: CallRecord, event_type: str) -> None:
    """向 supervisor 房间推 call.started / call.ended / call.aborted 事件。

    §9.3 —— 业主电话 owner_phone_masked 不在此处拼装：把密文 owner_phone_enc
    交给 SupervisorManager.broadcast，由其按每个订阅连接握手时的
    can_see_plaintext 快照逐一注入明文 / 脱敏值。
    """
    from app.risk.supervisor_manager import get_supervisor_manager

    caller = db.get(UserAccount, call.caller_user_id) if call.caller_user_id else None
    case = db.get(CollectionCase, call.case_id) if call.case_id else None
    owner = db.get(OwnerProfile, case.owner_id) if case and case.owner_id else None
    payload = {
        "type": event_type,  # "call.started" | "call.ended" | "call.aborted"
        "call_id": call.id,
        "case_id": call.case_id,
        "caller_user_id": call.caller_user_id,
        "caller_name": caller.name if caller else None,
        "owner_name": owner.name if owner else None,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "recording_mode": call.recording_mode,
        "status": call.status,
    }
    sup = get_supervisor_manager()
    await sup.broadcast(
        call.tenant_id, payload, owner_phone_enc=owner.phone_enc if owner else None
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_broadcast_call_event.py -v`
Expected: PASS —— 1 passed。

- [ ] **Step 5: 跑相邻回归（确认拨号链路不受影响）**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_dial_request.py tests/api/test_calls_qr_dial.py tests/api/test_supervisor_ws.py -v`
Expected: PASS —— 全绿。`_broadcast_call_event` 在无 supervisor 连接时 `broadcast` 遍历空房间为 no-op；这些测试不依赖 WS 广播 payload。

- [ ] **Step 6: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/api/calls_v1.py poc/backend/tests/api/test_broadcast_call_event.py
git commit -m "feat(v2.2): §9.3 _broadcast_call_event 改传密文 + 删硬编码 provider_id=None"
```

---

## Task 4: 标注设计文档 + 全量回归

**Files:**
- Modify: `docs/superpowers/specs/2026-05-16-role-model-refactor-design.md:183-187`（§9.3 段落）

- [ ] **Step 1: 标注 §9.3 已实现**

把 `docs/superpowers/specs/2026-05-16-role-model-refactor-design.md` 第 187 行末尾那句：

```
- 根治需在 `broadcast` 内按每个订阅连接的 `provider_id` 逐一脱敏(架构改动)。本次重构不做,代码已留 `TODO(v2.2-followup)`,作为后续独立需求记录。
```

替换为：

```
- 根治需在 `broadcast` 内按每个订阅连接的身份逐一脱敏(架构改动)。
- ✅ **已实现(2026-05-16)**:`SupervisorManager` 改为按连接存 `can_see_plaintext` 快照、`broadcast` 逐连接注入 `owner_phone_masked`;`ws_supervisor` 握手时算快照。详见 `docs/superpowers/specs/2026-05-16-ws-broadcast-phone-masking-design.md`。`TODO(v2.2-followup)` 已清除。
```

- [ ] **Step 2: 全量后端回归**

Run: `cd poc/backend && python3.12 -m pytest -q`
Expected: PASS —— 全量绿（基线 671 passed，本次新增 9 条 → 约 680 passed），无 ERROR / FAILED。

若有 FAIL，定位是否本次改动引入；`_broadcast_call_event` / `SupervisorManager` / `ws_supervisor` 相关失败必须修复后再继续。

- [ ] **Step 3: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add docs/superpowers/specs/2026-05-16-role-model-refactor-design.md
git commit -m "docs(v2.2): §9.3 标注已实现 + 清除 TODO 引用"
```

---

## Self-Review

**1. Spec coverage（对照设计文档 §3 / §6）：**
- §3.1 `SupervisorConn` dataclass → Task 1 Step 3 ✅
- §3.2 `_rooms` 改 dict、`connect` 改签名 → Task 1 Step 3 ✅
- §3.3 `broadcast` 逐连接注入 → Task 1 Step 3 ✅
- §3.4 `ws_supervisor` 握手快照 → Task 2 Step 3 ✅
- §3.5 `_broadcast_call_event` 调用方简化 → Task 3 Step 3 ✅
- §6 测试矩阵 6 条单测 → Task 1 Step 1 全部覆盖（plaintext / masked / mixed / no-phone / stale-key / disconnect）✅
- §6 集成测试（服务商督导脱敏）→ 设计文档允许降级；本计划 Task 2 用「握手快照」集成测试覆盖物业 + 服务商两侧 `can_see_plaintext`，Task 3 用契约测试覆盖调用方传密文。两者合起来等价覆盖端到端链路（密文→快照→broadcast 逐连接脱敏由 Task 1 单测验证），无需重复造完整 WS 广播 e2e ✅
- §7 文件清单 → 全部有对应 Task ✅

**2. Placeholder scan:** 无 TBD / TODO / 「类似 Task N」/ 「适当处理」。每个 code step 都给了完整代码与精确命令。✅

**3. Type consistency:**
- `SupervisorConn(can_see_plaintext: bool)` —— Task 1 定义、Task 2 测试 `conn.can_see_plaintext` 读取，一致 ✅
- `connect(tenant_id, ws, *, can_see_plaintext)` —— Task 1 定义、Task 2 调用，一致 ✅
- `broadcast(tenant_id, event, *, owner_phone_enc=None)` —— Task 1 定义、Task 3 调用 `broadcast(call.tenant_id, payload, owner_phone_enc=...)`、Task 3 测试 `_FakeManager.broadcast` 同签名，一致 ✅
- `should_reveal_owner_phone` / `is_provider_contract_active` —— 关键字参数与现有 `phone_visibility.py` 签名一致 ✅
