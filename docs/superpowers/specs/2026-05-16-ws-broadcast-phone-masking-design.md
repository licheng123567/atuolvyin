# §9.3 WS 广播逐订阅者电话脱敏 — 设计文档

> 来源：`docs/superpowers/specs/2026-05-16-role-model-refactor-design.md` §9「下游影响」第 3 项。
> 角色模型重构（PR #18）已落地，本文档是其三个下游需求中的第一个（§9.3 → §9.1 → §9.2）。

**日期：** 2026-05-16
**分支：** `feat/v2.2-app-ux-fixes`

---

## 1. 问题陈述

实时通话墙通过 WebSocket（`/ws/supervisor`）向某 `tenant_id` 房间内的所有订阅者群发
`call.started` / `call.ended` / `call.aborted` 事件，payload 含业主电话字段
`owner_phone_masked`。

当前 `app/api/calls_v1.py::_broadcast_call_event` 在构造 payload 时**硬编码**
`should_reveal_owner_phone(role="supervisor", provider_id=None)` —— 即把所有订阅者
当作「物业内部 supervisor」处理，必然返回明文电话。

角色模型重构后，服务商侧督导（`role='supervisor'` 且 `provider_id` 非空）可以连入
**同一个 `tenant_id` 房间**（物业把项目外包给服务商时）。结果：

- **服务商督导无论合同是否有效，都会收到明文业主电话。**
- 这违反 `phone_visibility.py` 既定策略：服务商侧应当「合同 active && 项目未过期 →
  明文，否则脱敏」。

`_broadcast_call_event` 第 298-301 行已有 `TODO(v2.2-followup)` 注释标记此缺口。
本设计即根治该 TODO。

### 范围

- **仅** `/ws/supervisor` 实时通话墙广播路径。
- REST 端点（列表 / 详情）已在角色重构中接入 `should_reveal_owner_phone`，不在本范围。
- 不改 WS 鉴权、房间分组（仍按 `tenant_id`）、事件类型、字段名。

---

## 2. 核心思路

**WS 群发无法在「发送时」知道每个订阅者的身份** —— 身份只在「连接建立时」由 token 已知。

因此：**在 WS 握手时把「该连接能否看明文」算成一个布尔快照，存进连接对象；广播时按
每个连接的布尔值分别注入脱敏 / 明文电话。**

这把「逐订阅者脱敏」从一个无法解的群发问题，降维成「连接建立时算一次 + 广播时按连接
查表」。

---

## 3. 组件设计

### 3.1 `SupervisorConn` —— 连接级身份快照

`app/risk/supervisor_manager.py` 新增轻量 dataclass：

```python
from dataclasses import dataclass

@dataclass(slots=True)
class SupervisorConn:
    """单个 supervisor WS 连接的身份快照。在 WS 握手时算一次，连接生命周期内不变。"""
    can_see_plaintext: bool
```

只存一个布尔。不存 `role` / `provider_id` —— 那些只在握手时用于推导 `can_see_plaintext`，
之后不再需要。

### 3.2 `SupervisorManager` —— 房间结构改造

`_rooms` 从 `dict[int, set[WebSocket]]` 改为
`dict[int, dict[WebSocket, SupervisorConn]]`：

```python
self._rooms: dict[int, dict[WebSocket, SupervisorConn]] = defaultdict(dict)
```

方法签名变化：

| 方法 | 旧签名 | 新签名 |
|------|--------|--------|
| `connect` | `connect(tenant_id, ws)` | `connect(tenant_id, ws, *, can_see_plaintext: bool)` |
| `disconnect` | `disconnect(tenant_id, ws)` | 不变 |
| `broadcast` | `broadcast(tenant_id, event)` | `broadcast(tenant_id, event, *, owner_phone_enc: str \| None = None)` |

- `connect`：`self._rooms[tenant_id][ws] = SupervisorConn(can_see_plaintext=can_see_plaintext)`
- `disconnect`：`self._rooms[tenant_id].pop(ws, None)`，房间空则删 key（逻辑同今天）。
- `broadcast`：见 3.3。

### 3.3 `broadcast` —— 逐连接注入电话

```python
async def broadcast(
    self,
    tenant_id: int,
    event: dict,
    *,
    owner_phone_enc: str | None = None,
) -> None:
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
```

要点：

- `owner_phone_enc=None` 时 `broadcast` 行为与今天完全一致（向后兼容，其它调用方不受影响）。
- `owner_phone_enc` 非空时，调用方**不再**自己放 `owner_phone_masked` 进 `event`；
  由 `broadcast` 逐连接覆盖。
- `display_owner_phone` 从 `app/core/phone_visibility.py` import。
- 当 `owner_phone_enc` 非空但调用方仍在 `event` 里塞了 `owner_phone_masked` 键，
  `{**event, "owner_phone_masked": ...}` 会覆盖它 —— 安全兜底。

### 3.4 `ws_supervisor` —— 握手时算快照

`app/api/ws_supervisor.py`，在 `manager.connect(...)` 调用前插入快照计算：

```python
provider_id = payload.get("provider_id")  # None=物业内部, 非空=服务商侧

if provider_id is None:
    # 物业内部 supervisor / admin / project_manager —— 永远明文
    can_see_plaintext = True
else:
    # 服务商侧 —— 连接时快照合同有效性
    contract_active = is_provider_contract_active(db, tenant_id, provider_id)
    can_see_plaintext = should_reveal_owner_phone(
        role=role,
        provider_id=provider_id,
        contract_active=contract_active,
        project_active=True,  # 见 §4 简化说明
    )

await manager.connect(tenant_id, websocket, can_see_plaintext=can_see_plaintext)
```

- FastAPI WebSocket 端点支持 `Depends` —— 给 `ws_supervisor` 函数签名加
  `db: Annotated[Session, Depends(get_db)]`，与现有 `app/api/ws_calls.py` 的取
  session 方式一致。无需手动开 `SessionLocal`。
- `role` 已在上文从 `payload.get("role", "")` 取出并校验过 `_SUPERVISOR_ROLES`。
- import：`from app.core.db import get_db`、`from sqlalchemy.orm import Session`、
  `from app.core.phone_visibility import is_provider_contract_active, should_reveal_owner_phone`

### 3.5 `_broadcast_call_event` —— 调用方简化

`app/api/calls_v1.py::_broadcast_call_event`：

- **删除** 第 298-301 行 `TODO(v2.2-followup)` 注释块。
- **删除** `_bc_reveal = should_reveal_owner_phone(role="supervisor", provider_id=None)` 行。
- payload 字典中**删除** `owner_phone_masked` 键（改由 `broadcast` 逐连接注入）。
- `broadcast` 调用改为传 `owner_phone_enc`：

```python
payload = {
    "type": event_type,
    "call_id": call.id,
    "case_id": call.case_id,
    "caller_user_id": call.caller_user_id,
    "caller_name": caller.name if caller else None,
    "owner_name": owner.name if owner else None,
    # owner_phone_masked 不在此处 —— 由 SupervisorManager.broadcast 逐连接注入
    "started_at": call.started_at.isoformat() if call.started_at else None,
    "recording_mode": call.recording_mode,
    "status": call.status,
}
sup = get_supervisor_manager()
await sup.broadcast(call.tenant_id, payload, owner_phone_enc=owner.phone_enc if owner else None)
```

- `should_reveal_owner_phone` / `display_owner_phone` 在 `calls_v1.py` 若无其它引用，
  一并清理 import。

---

## 4. 简化与权衡（用户已确认）

| 决策 | 选择 | 权衡 |
|------|------|------|
| 合同有效性检查时机 | **WS 连接握手时快照一次** | 合同在会话中途被解约 → 服务商督导仍看明文，直到下次重连。窗口极短（督导会话通常分钟级），可接受。替代方案「每次广播查合同」会给热路径加 N 次 DB 查询。 |
| `project_active` | **固定 `True`** | 广播事件不绑定单个项目语境，无法在握手时确定「当前项目」。固定 True 等价于「不因项目过期而额外脱敏」；合同有效性已是主闸门。后续若需精确化，可在 §9.1/§9.2 迭代。 |

这两条权衡都倾向「实现简单、热路径零额外查询」，代价是一个极短的脱敏延迟窗口。
用户在 brainstorming 阶段已明确接受。

---

## 5. 安全影响

- **修复方向是收紧权限**：服务商侧督导在合同失效时，从「收到明文」变为「收到脱敏」。
  不存在「本来脱敏现在变明文」的反向风险。
- 物业内部 supervisor / admin / project_manager（`provider_id=None`）行为不变 —— 仍明文。
- 平台角色（superadmin / ops）不在 `_SUPERVISOR_ROLES`，无法连入此 WS，不受影响。
- `owner_phone_enc` 是 AES-256 密文，仅在 `display_owner_phone` 内按连接解密；
  密文本身不会出现在 payload。

---

## 6. 测试设计

新增 `poc/backend/tests/risk/test_supervisor_manager.py`（若 `tests/risk/` 不存在则建）。
`SupervisorManager` 是纯内存对象，用 fake WebSocket（记录 `send_json` 入参的 stub）
即可单测，无需 testcontainers。

| 测试 | 场景 | 断言 |
|------|------|------|
| `test_broadcast_plaintext_connection` | `can_see_plaintext=True` 连接 + `owner_phone_enc` | 收到的 `owner_phone_masked` 是 11 位明文 |
| `test_broadcast_masked_connection` | `can_see_plaintext=False` 连接 + `owner_phone_enc` | 收到的 `owner_phone_masked` 是 `138****1234` 形式 |
| `test_broadcast_mixed_room` | 同一房间一个明文连接 + 一个脱敏连接 | 各自收到对应形式（明文连接拿明文，脱敏连接拿脱敏） |
| `test_broadcast_no_owner_phone` | `owner_phone_enc=None` | payload 原样下发，行为与改造前一致 |
| `test_broadcast_event_overwrites_stale_key` | `event` 里塞了假 `owner_phone_masked` + 传 `owner_phone_enc` | 收到的值是按连接重算的，不是 event 里的假值 |
| `test_disconnect_removes_conn` | connect 后 disconnect | 房间清空，再 broadcast 不报错 |

集成层：`tests/ws/test_ws_calls_e2e.py` 已覆盖 WS 握手 + 广播链路。新增一条
`tests/ws/` 用例，用服务商督导 token（`provider_id` 非空、无有效合同）连接，
触发一次 `call.started` 广播，断言收到的 `owner_phone_masked` 是脱敏形式。
若该集成用例因 token / seed 数据装配成本过高，可降级为只跑上表 6 条单测 +
对 `ws_supervisor` 快照分支的针对性单测。

---

## 7. 文件清单

| 文件 | 操作 |
|------|------|
| `poc/backend/app/risk/supervisor_manager.py` | 改：新增 `SupervisorConn`；`_rooms` 改 dict；`connect` / `broadcast` 改签名 |
| `poc/backend/app/api/ws_supervisor.py` | 改：握手时算 `can_see_plaintext` 快照并传入 `connect` |
| `poc/backend/app/api/calls_v1.py` | 改：`_broadcast_call_event` 删 TODO、删硬编码 reveal、改传 `owner_phone_enc` |
| `poc/backend/tests/risk/test_supervisor_manager.py` | 建：6 条单测 |
| `poc/backend/tests/ws/test_ws_calls_e2e.py` | 改：补 1 条服务商督导脱敏集成用例（可选降级） |
| `docs/superpowers/specs/2026-05-16-role-model-refactor-design.md` | 改：§9.3 标注「已实现，见本文档」 |

无 DB 迁移、无 schema 变更、无前端 / Android 改动（字段名 `owner_phone_masked` 不变，
前端不感知）。
