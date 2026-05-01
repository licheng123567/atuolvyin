# Sprint 4 设计文档 — 实时 WebSocket 通话辅助

## 目标

在 Sprint 3a/3b 已交付的「录音上传 + 事后 ASR/LLM 分析 + PC 详情页 + Android JWT 迁移」之上，打通**实时通话辅助**的端到端主路径：

- Android App 录音 → WebSocket 推流 → 后端流式 ASR → 实时 AI 话术卡片
- PC 触发拨号（DIAL_REQUEST）→ 小米推送 → App 唤起接单
- 通话后 AI 预填标记 → 员工确认 → 落库 AnalysisResult

**降级路径**：WS 失败/弱网时，自动切换为「本地录音 + 复用 Sprint 3a 的事后上传流」。

**核心 KPI**：AI 话术卡片首条延迟 ≤ 3s（P90）。

**不在 Sprint 4 范围内**：
- 华为 / OPPO 推送（仅小米）
- 浮动按钮中的「建工单」「转法务」「转接」（Sprint 5+）
- 多 worker WebSocket 广播（v1.1）
- 风控 L1/L2/L3 实时干预（v1.1）

---

## 架构概览

### 端到端时序

```
PC 端                   后端 (FastAPI + Celery)         Android (Kotlin)
 │                            │                            │
 │ 1. POST /calls/dial-request│                            │
 ├───────────────────────────►│                            │
 │     {case_id}              │                            │
 │ ◄──{call_id}───────────────┤                            │
 │                            │ 2. MiPush 推送             │
 │                            ├───────────────────────────►│
 │                            │   {call_id, case_id, ...}  │
 │ 3. WS /ws/calls/{call_id}  │                            │
 │      ?role=agent           │ 4. 用户点通知打开 Activity │
 ├───────────────────────────►│                            │
 │                            │ 5. WS /ws/calls/{call_id}  │
 │                            │      ?role=agent           │
 │                            │◄───────────────────────────┤
 │                            │ 6. {type:"call.started"}   │
 │                            │◄───────────────────────────┤
 │ ◄─────────广播─────────────┤                            │
 │                            │ 7. 二进制音频帧（每 100ms）│
 │                            │◄───────────────────────────┤
 │                            │ 8. → DashScope 流式 ASR    │
 │ 9. {transcript.chunk}      │                            │
 │ ◄──广播──┬─────────────────┤────────────────────────────►
 │          │                 │ 10. 累积文本 → LLM 建议     │
 │ {suggestion.ready}         │                            │
 │ ◄──广播──┴─────────────────┤────────────────────────────►
 │                            │                            │
 │ 11. POST /suggestions/{id}/feedback                     │
 │ ◄──or──────────────────────┤◄───────────────────────────┤
 │                            │                            │
 │                            │ 12. {call.ended}           │
 │                            │◄───────────────────────────┤
 │                            │ 13. 最终 LLM 分析+落库     │
 │ 14. {tag.ready,…}          │                            │
 │ ◄──广播──┬─────────────────┤────────────────────────────►
 │                            │ 15. PostCallTagDialog 展示 │
 │                            │ 16. PATCH /calls/{id}/tag  │
 │                            │◄───────────────────────────┤
```

### 关键架构选择

| 项 | 选择 | 理由 |
|----|------|------|
| WebSocket 服务器 | FastAPI 内置 `WebSocket` | 与现有 HTTP 同进程，零额外服务 |
| 多实例广播 | 暂不做（单 worker） | MVP 单租户并发通话 < 100，足够 |
| 音频帧编码 | 二进制 PCM 16kHz mono 16-bit | DashScope paraformer-realtime-v2 要求 |
| 音频帧大小 | 100ms / 3200 字节 | 与 DashScope SDK 默认对齐，行业标准 |
| 流式 ASR backend | `dashscope` + `mock`，dispatcher 模式 | 复用现有 `app/services/asr.py` 模式 |
| LLM 触发节奏 | utterance-end + 5s debounce + 20s 超时兜底 | 行业实践（Cresta/Gong），贴合催收场景 |
| 降级路径 | WS 重连 ≥ 3 次失败 → 本地录音 + Sprint 3a 事后上传 | 复用现有上传链路 |
| WS 鉴权 | query string `?token=<jwt>` | 与 HTTP API 同源 JWT |
| 推送通道 | 小米 MiPush（Sprint 4 唯一） | 测试机为 MIUI；华为/OPPO 推到 Sprint 5 |

---

## Section 1：后端 — WebSocket 基础设施

### 1.1 文件结构

```
poc/backend/app/
├── ws/                                    [新增模块]
│   ├── __init__.py
│   ├── connection_manager.py              ConnectionManager（房间广播）
│   ├── call_session.py                    每通话状态聚合（ASR + LLM）
│   └── auth.py                            WS JWT 鉴权辅助
├── api/
│   └── ws_calls.py                        [新] WebSocket 端点
└── core/config.py                         [改] 新增 settings
```

### 1.2 ConnectionManager

```python
class ConnectionManager:
    def __init__(self):
        self._rooms: dict[int, dict[WebSocket, str]] = defaultdict(dict)
        self._lock = asyncio.Lock()
    
    async def connect(self, call_id: int, ws: WebSocket, role: str): ...
    async def disconnect(self, call_id: int, ws: WebSocket): ...
    async def broadcast(self, call_id: int, message: dict, exclude: WebSocket | None = None): ...
    async def send_to_role(self, call_id: int, role: str, message: dict): ...
```

模块级单例，与 FastAPI app 实例共生命周期。

### 1.3 WebSocket 端点

```
GET /ws/calls/{call_id}?token=<jwt>&role=<agent|observer>
```

**鉴权与访问控制**：
- `role=agent`：要求 `call.assigned_to == user.id` 且 user.tenant_id 匹配。同一 user 可同时从 PC 和 Android 各开一条 agent 连接（通过 JWT user_id 识别同一身份）。
- `role=observer`：要求 user.role ∈ {admin, supervisor} 且 tenant_id 匹配 case.tenant_id
- JWT 失败或越权 → close(code=1008, reason="policy violation")

**音频帧来源约束**：
- 仅 `role=agent` 可发送二进制音频帧；`role=observer` 发二进制帧服务端忽略
- 实践中 PC（agent role）不发音频，只 Android 发；服务端 MVP 不强制单 sender，由客户端自律
- 若同一 call 多个 agent 连接同时发音频（异常情况），服务端按到达顺序串接转发给 ASR；最终事后录音（Sprint 3a 上传）做兜底校正

### 1.4 消息协议

**Client → Server**

| 帧类型 | type | Payload | 谁发 |
|--------|------|---------|------|
| 二进制 | （无） | PCM 16kHz mono 16-bit, 3200 字节 | 仅 agent |
| JSON | `call.started` | `{}` | agent |
| JSON | `call.ended` | `{}` | agent |
| JSON | `suggestion.feedback` | `{id, action: "adopt"|"ignore"}` | agent |
| JSON | `ping` | `{}` | 任何 |

**Server → Client**

| type | Payload |
|------|---------|
| `transcript.chunk` | `{seq, speaker, text, ts, utterance_end?: bool}` |
| `suggestion.ready` | `{id, text, intent, confidence}` |
| `tag.ready` | `{intent, promise_date?, promise_amount?, summary}` |
| `call.error` | `{code, message}` |
| `pong` | `{}` |

---

## Section 2：后端 — 流式 ASR 服务

### 2.1 dispatcher 模式

```python
# app/services/streaming_asr.py
class StreamingASRSession(Protocol):
    async def feed_audio(self, pcm_bytes: bytes) -> None: ...
    async def close(self) -> None: ...

class StreamingASRBackend(Protocol):
    async def open_session(
        self,
        on_transcript: Callable[[TranscriptChunk], Awaitable[None]],
        on_error: Callable[[Exception], Awaitable[None]],
    ) -> StreamingASRSession: ...

def get_streaming_asr_backend() -> StreamingASRBackend:
    if settings.streaming_asr_backend == "dashscope":
        return DashScopeStreamingASR()
    return MockStreamingASR()
```

### 2.2 DashScope 实现

包装 `dashscope.audio.asr.Recognition`（同步 SDK）：
- 用 `asyncio.run_in_executor` 包裹 `feed_audio`
- 通过 `RecognitionCallback` 接收回调，转发到 `on_transcript`
- 模型参数：`model="paraformer-realtime-v2"`, `format="pcm"`, `sample_rate=16000`

### 2.3 Mock 实现

每接收 1s 累积音频（10 帧）返回一段固定文本块：

```python
class MockStreamingASR:
    async def open_session(self, on_transcript, on_error):
        return MockSession(on_transcript)

class MockSession:
    SAMPLES = ["您好哪位", "我现在没钱", "下个月发工资再说"]
    
    async def feed_audio(self, pcm_bytes):
        self._buffer += len(pcm_bytes)
        if self._buffer >= 32000:  # ~1s
            text = self.SAMPLES[self._index % len(self.SAMPLES)]
            await self._on_transcript(TranscriptChunk(seq=self._seq, speaker="customer", text=text, ts=now(), utterance_end=True))
            self._buffer = 0
            self._index += 1
            self._seq += 1
```

---

## Section 3：后端 — 实时 LLM 建议引擎

```python
# app/services/realtime_llm.py
class RealtimeSuggestionEngine:
    UTTERANCE_SILENCE_MS = 1500
    DEBOUNCE_SEC = 5
    TIMEOUT_FALLBACK_SEC = 20
    
    def __init__(self, case: CollectionCase, owner: OwnerProfile):
        self._buffer: list[TranscriptChunk] = []
        self._last_llm_at: float = 0
        self._case = case
        self._owner = owner
    
    async def on_transcript(self, chunk: TranscriptChunk) -> Optional[Suggestion]:
        self._buffer.append(chunk)
        now = time.monotonic()
        
        debounce_ok = (now - self._last_llm_at) >= self.DEBOUNCE_SEC
        timeout_hit = (now - self._last_llm_at) >= self.TIMEOUT_FALLBACK_SEC
        
        if (chunk.utterance_end and debounce_ok) or timeout_hit:
            self._last_llm_at = now
            return await self._call_llm()
        return None
    
    async def on_call_ended(self) -> AnalysisResult:
        # 最终一次完整分析，落库
        ...
```

LLM 调用复用现有 `app/services/llm.py`（`LLM_BACKEND=mock` 在测试时可用）。

输入上下文：业主姓名 / 房号 / 欠费金额 / 历史最后 3 通话摘要 + 当前通话累积 transcript。

---

## Section 4：后端 — MiPush 客户端

### 4.1 API 封装

```python
# app/services/mipush.py
class MiPushClient(Protocol):
    async def send_to_user(
        self,
        reg_id: str,
        payload: dict,
        title: str,
        description: str,
    ) -> None: ...

class XiaomiMiPushClient:
    URL = "https://api.xmpush.xiaomi.com/v3/message/regid"
    
    def __init__(self, app_secret: str, package_name: str):
        self._app_secret = app_secret
        self._package_name = package_name
    
    async def send_to_user(self, reg_id, payload, title, description):
        async with httpx.AsyncClient(timeout=5) as cli:
            resp = await cli.post(self.URL, headers={
                "Authorization": f"key={self._app_secret}",
            }, data={
                "registration_id": reg_id,
                "restricted_package_name": self._package_name,
                "payload": json.dumps(payload),
                "title": title,
                "description": description,
                "pass_through": 0,  # 0 = 通知栏消息
                "notify_type": -1,  # 默认提示
            })
            resp.raise_for_status()

class MockMiPushClient:
    def __init__(self):
        self.sent_messages: list[dict] = []
    
    async def send_to_user(self, reg_id, payload, title, description):
        self.sent_messages.append({
            "reg_id": reg_id, "payload": payload, "title": title, "description": description
        })
```

### 4.2 Settings 扩展

```python
class Settings:
    streaming_asr_backend: Literal["dashscope", "mock"] = "mock"
    mipush_backend: Literal["xiaomi", "mock"] = "mock"
    mipush_app_secret: str | None = None
    mipush_package_name: str | None = None
    realtime_llm_debounce_sec: int = 5
    realtime_llm_timeout_sec: int = 20
```

---

## Section 5：后端 — HTTP API 扩展

### 5.1 POST `/api/v1/calls/dial-request`

**Request**：
```json
{ "case_id": 1023 }
```

**流程**：
1. 校验 `case.tenant_id == user.tenant_id` 且 `case.assigned_to == user.id`
2. INSERT `CallRecord(status="pending_dial", started_at=NULL)`
3. 查 `device_profile WHERE user_id=user.id ORDER BY updated_at DESC LIMIT 1`
4. 如 `push_reg_id IS NULL` → 422 `ERR_PUSH_NOT_REGISTERED`
5. 调 `MiPushClient.send_to_user(reg_id, payload={type:"DIAL_REQUEST", call_id, case_id, owner_name, owner_phone_masked})`
6. 返回 `{call_id, status: "dispatched"}`

**Response**：
```json
{ "call_id": 4711, "status": "dispatched" }
```

### 5.2 PATCH `/api/v1/calls/{call_id}/tag`

**Request**：
```json
{
  "intent": "promise_pay",
  "promise_date": "2026-05-10",
  "promise_amount": 2400,
  "notes": "等下个月发工资"
}
```

**流程**：
1. 校验 `call.agent_id == user.id`
2. 更新 `AnalysisResult` 对应字段（`key_segments` 中的 intent 等 + `summary`），写 `call.user_confirmed_at = now()`
3. 返回更新后的 `AnalysisResult`

### 5.3 POST `/api/v1/calls/{call_id}/suggestions/{suggestion_id}/feedback`

**Request**：
```json
{ "action": "adopt" }
```

**流程**：
1. INSERT `suggestion_feedback`（**Sprint 4 新建表**，见 §6.1）
2. `suggestion_id` 作 idempotency key（unique 约束 (call_id, suggestion_id)，重复提交返回 200 不重复写入）

### 5.4 POST `/api/v1/devices/register`（已存在，扩展）

新增字段：`push_reg_id: str | None`、`push_provider: str | None = "xiaomi"`。

---

## Section 6：数据模型变更

### 6.1 Alembic 4-001

```python
def upgrade():
    op.add_column("device_profile",
        sa.Column("push_reg_id", sa.Text, nullable=True))
    op.add_column("device_profile",
        sa.Column("push_provider", sa.String(20), nullable=True))
    op.add_column("call_record",
        sa.Column("user_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    
    # 新建表：实时建议反馈
    op.create_table(
        "suggestion_feedback",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("call_id", sa.BigInteger, sa.ForeignKey("call_record.id"), nullable=False),
        sa.Column("suggestion_id", sa.String(64), nullable=False),  # 服务端生成的 UUID
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),  # "adopt" | "ignore"
        sa.Column("suggestion_text", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("call_id", "suggestion_id", name="uq_suggestion_feedback_call_sid"),
    )
    op.create_index("ix_suggestion_feedback_call_id", "suggestion_feedback", ["call_id"])
```

### 6.2 ORM 模型修改

- `app/models/device.py`：`DeviceProfile` 加 `push_reg_id`、`push_provider`
- `app/models/call.py`：`CallRecord` 加 `user_confirmed_at`；新增 `SuggestionFeedback` 类

### 6.3 status 枚举扩展（应用层）

`call_record.status` 当前已有：`queued | processing | processed | failed`

新增（仅应用层校验，DB 层不强约束）：
- `pending_dial` — DIAL_REQUEST 已发，App 未接单
- `live` — 通话进行中
- `live_ended_pending_analysis` — 已挂机，等最终 LLM

挂机后服务端落最终分析 → status 变 `processed`（与 Sprint 3b 对齐）。

---

## Section 7：Android 设计

### 7.1 文件结构

```
poc/android/app/src/main/java/com/autoluyin/demo/
├── push/
│   ├── MiPushService.kt
│   └── DialRequestHandler.kt
├── realtime/
│   ├── RealtimeCallActivity.kt
│   ├── AudioStreamClient.kt
│   ├── PostCallTagDialog.kt
│   ├── TranscriptAdapter.kt
│   └── SuggestionCardView.kt
├── api/
│   └── RealtimeApi.kt
├── Api.kt                                 [改] push_reg_id 上报
├── AppConfig.kt                           [改] 持久化 push_reg_id
└── AndroidManifest.xml                    [改] MiPush + Activity 锁屏唤醒
```

### 7.2 MiPush 集成

**Gradle**：
```gradle
implementation 'com.xiaomi.mipush.sdk:MiPushClient:6.0.0-RELEASE'
```

**MiPushService**：
```kotlin
class MiPushService : PushMessageReceiver() {
    override fun onCommandResult(ctx: Context, msg: MiPushCommandMessage) {
        if (msg.command == MiPushClient.COMMAND_REGISTER && msg.resultCode == 0L) {
            val regId = msg.commandArguments[0]
            AppConfig.savePushRegId(ctx, regId)
            ApiClient.get(ctx).registerDevice(regId)
        }
    }
    
    override fun onNotificationMessageClicked(ctx: Context, msg: MiPushMessage) {
        val payload = JSONObject(msg.content)
        if (payload.getString("type") == "DIAL_REQUEST") {
            DialRequestHandler.handle(ctx, payload)
        }
    }
}
```

`MainActivity.onCreate()` 末尾追加 `MiPushClient.registerPush(applicationContext, APP_ID, APP_KEY)`。

### 7.3 RealtimeCallActivity 布局

四区：
1. **顶部通话控制栏**：通话时长 timer + 静音 + 免提 + 挂断
2. **业主信息卡片**：姓名 / 房号 / 欠费金额 / 上次联系
3. **ASR 滚动 RecyclerView**：自动滚到底
4. **AI 话术卡片**：最新一条 + 采用/忽略按钮
5. **浮动按钮（右下角竖排）**：💰 二维码 + 📋 建工单（建工单 Sprint 5 接入）

启动时序：
1. Intent 携带 `case_id` + `call_id`
2. `GET /agent/cases/{case_id}` 拉业主信息
3. 实拨电话（`Intent(Intent.ACTION_CALL, Uri.parse("tel:..."))`）
4. `AudioStreamClient.start(call_id)` → AudioRecord + WS 启动
5. 收 `tag.ready` → 弹 PostCallTagDialog

### 7.4 AudioStreamClient

```kotlin
class AudioStreamClient(
    private val callId: Long,
    private val token: String,
    private val onTranscript: (TranscriptChunk) -> Unit,
    private val onSuggestion: (Suggestion) -> Unit,
    private val onTagReady: (TagPayload) -> Unit,
    private val onStateChange: (State) -> Unit,
) {
    enum class State { NORMAL, DEGRADED, FALLBACK_LOCAL }
    
    private val FRAME_MS = 100
    private val SAMPLE_RATE = 16000
    private val FRAME_BYTES = SAMPLE_RATE / 1000 * FRAME_MS * 2  // 3200
    private val sendQueue = LinkedBlockingQueue<ByteArray>(50)  // 5s 缓冲
    
    fun start() { /* 录音线程 + 发送线程 + WS 连接 */ }
    fun stop() { /* 发送 call.ended，关闭 WS，停止 recorder */ }
}
```

线程模型：
- 录音线程：`AudioRecord` 阻塞读 → 切 100ms 帧 → `sendQueue.offer()`
- 发送线程：`sendQueue.take()` → 二进制帧推 WS（队列满则丢最早 5 帧 + 标记 DEGRADED）
- WS 接收回调：在 OkHttp 线程，`mainHandler.post {}` 派发到 UI

### 7.5 网络降级状态机

```
NORMAL ──ws.latency >2s 持续 5s──→ DEGRADED
              │                         │
              │                  本地继续录音到文件
              │                  WS 持续重连（指数退避）
              │                         │
              │←──重连成功──────────────┘
              │
              └──重连 ≥3 次失败 或 ≥10s 全失──→ FALLBACK_LOCAL
                                                    │
                                  停 WS，本地录音直到挂机
                                  挂机后用 Sprint 3a 的 POST /calls/upload
```

UI 徽章：🟢 NORMAL / 🟡 DEGRADED / 🔵 FALLBACK_LOCAL

### 7.6 PostCallTagDialog

```
┌──────────────────────────────────┐
│ 通话标记                         │
├──────────────────────────────────┤
│ 客户意图：[承诺缴费 ▼]           │  ← AI 预填
│ 承诺日期：[2026-05-10]           │  ← AI 预填
│ 备注：    [等下个月发工资...]    │  ← AI 预填
│                                  │
│  [取消]              [提交]      │
└──────────────────────────────────┘
```

提交：`PATCH /api/v1/calls/{call_id}/tag`，成功后回任务列表（首页）。

### 7.7 AndroidManifest 关键变更

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.CALL_PHONE" />
<uses-permission android:name="android.permission.READ_PHONE_STATE" />

<receiver android:name=".push.MiPushService"
          android:exported="true">
    <intent-filter>
        <action android:name="com.xiaomi.mipush.RECEIVE_MESSAGE" />
    </intent-filter>
</receiver>

<activity android:name=".realtime.RealtimeCallActivity"
          android:launchMode="singleTask"
          android:showWhenLocked="true"
          android:turnScreenOn="true" />
```

`showWhenLocked` + `turnScreenOn` 确保 MiPush 通知点击后 Activity 直接覆盖锁屏。

---

## Section 8：PC 前端设计

### 8.1 文件结构

```
frontend/src/
├── pages/agent/workstation/live.tsx              [新]
├── pages/admin/workstation/live.tsx              [新]
├── components/realtime/
│   ├── RealtimeCallShell.tsx                     [新] 三栏壳
│   ├── TranscriptStream.tsx                      [新] 中栏
│   ├── SuggestionCardStack.tsx                   [新] 右栏
│   └── ConnectionBadge.tsx                       [新]
├── lib/realtime/
│   ├── ws-client.ts                              [新]
│   └── types.ts                                  [新]
├── hooks/
│   └── useCallSocket.ts                          [新]
└── App.tsx                                       [改] 新增路由
```

### 8.2 ws-client.ts

```ts
interface CallSocketOptions {
  callId: number;
  role: "agent" | "observer";
  token: string;
  onTranscript: (chunk: TranscriptChunk) => void;
  onSuggestion: (s: Suggestion) => void;
  onTagReady: (tag: TagPayload) => void;
  onStatusChange: (status: "connected" | "reconnecting" | "failed" | "call_ended") => void;
}

export function openCallSocket(opts: CallSocketOptions): {
  close: () => void;
  sendFeedback: (id: string, action: "adopt" | "ignore") => void;
};
```

实现要点：
- 重连指数退避：1s / 2s / 4s / 8s（封顶 8s，无限重试）
- 心跳：每 30s 发 `{type:"ping"}`，60s 内无 `pong` 视失联

### 8.3 自动弹出机制

催收员 PC 端 `agent/cases` 列表点「拨打」：
1. POST `/api/v1/calls/dial-request` 拿 `call_id`
2. `navigate("/agent/workstation/{call_id}")`

工作台页 `mount` 时：
1. URL 解析 `call_id`
2. `useCallSocket({ role: "agent" })` 启动 WS
3. `useOne({ resource: "agent/cases", id: caseId })` 拉业主信息
4. 收 `tag.ready` → 跳转 `/calls/{call_id}` 详情页

> 注：催收员 PC 与 Android 同房间但只消费广播。**Android 是音频生产者，PC 与 Android 都是 ASR/Suggestion 消费者**。

### 8.4 三栏布局

```
┌──────────────────────────────────────────────────────────────────────┐
│  顶部状态栏：通话 03:42 · 🟢 实时 · 业主：张某某 · case #1023        │
│  ┌─────────────────┬───────────────────────┬────────────────────┐  │
│  │ 左：业主信息     │ 中：ASR 实时滚动       │ 右：AI 卡片栈       │  │
│  │ 280px           │ 1fr                   │ 320px              │  │
│  │                 │                       │                    │  │
│  │ 张某某          │ [客户] 您好           │ 💡 建议询问分期      │  │
│  │ 3-2-101         │ [我]   您好这里...    │ [采用] [忽略]       │  │
│  │ 欠费 ¥2,400     │ [客户] 我现在没钱      │                    │  │
│  │                 │ ...                   │ ── 历史（折叠）     │  │
│  │ [发二维码]      │                       │ • 询问家庭情况      │  │
│  │ ConnectionBadge │                       │ • ...               │  │
│  └─────────────────┴───────────────────────┴────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

样式遵守 CLAUDE.md：shadcn/ui + lucide-react + design token CSS 变量。

### 8.5 管理员旁听（observer）

`/admin/workstation/:call_id`：
- 复用 `RealtimeCallShell` 但 `role="observer"`
- 不显示「采用/忽略」按钮
- 顶部多一行「正在旁听 · 催收员：李明」
- 入口：admin/cases/:id 案件详情页的「正在通话中」徽章点入

### 8.6 路由变更

```tsx
// resources
{ name: "agent/workstation", show: "/agent/workstation/:call_id" },
{ name: "admin/workstation", show: "/admin/workstation/:call_id" },

// Routes
<Route path="/agent/workstation/:call_id" element={<AgentLiveWorkstation />} />
<Route path="/admin/workstation/:call_id" element={<AdminLiveWorkstation />} />
```

---

## Section 9：测试策略

### 9.1 后端（pytest + httpx + testcontainers-postgres）

| 测试文件 | 重点 |
|---------|------|
| `tests/services/test_streaming_asr_mock.py` | MockStreamingASR 喂入音频 → 收到固定文本块 |
| `tests/services/test_realtime_llm_engine.py` | utterance-end / debounce / timeout 三种触发条件 |
| `tests/services/test_mipush_mock.py` | MockMiPushClient 捕获参数；payload 字段完整 |
| `tests/api/test_dial_request.py` | 成功路径、未分配、无 reg_id、跨租户 |
| `tests/api/test_call_tag_patch.py` | 仅本人可改、字段更新、user_confirmed_at 写入 |
| `tests/ws/test_ws_calls_auth.py` | 越权 close 1008、无 token 拒绝、observer 跨租户拒绝 |
| `tests/ws/test_ws_calls_e2e.py` | mock ASR + mock LLM 跑通整条链路 |
| `tests/ws/test_ws_calls_degraded.py` | 慢消费者背压、断开后状态清理 |

### 9.2 Android（JUnit5 + MockK + Robolectric）

| 测试 | 重点 |
|------|------|
| `MiPushReceiverTest` | DIAL_REQUEST 解析、reg_id 持久化 |
| `AudioStreamClientTest` | 队列背压、降级状态机三态切换 |
| `RealtimeCallActivityTest` | tag.ready 弹窗、采用/忽略反馈 POST |

### 9.3 PC 前端（Vitest + RTL）

| 测试 | 重点 |
|------|------|
| `ws-client.test.ts` | 重连指数退避、心跳超时 |
| `RealtimeCallShell.test.tsx` | transcript 流增量渲染、suggestion 卡片切换 |

### 9.4 集成测试不接真服务

Sprint 4 默认 `STREAMING_ASR_BACKEND=mock`、`MIPUSH_BACKEND=mock`、`LLM_BACKEND=mock`。生产配置由运维切换。

---

## Section 10：风险与 Mitigations

| 风险 | 影响 | Mitigation |
|------|------|-----------|
| DashScope 流式 SDK 在 asyncio 中不稳定 | 后端 ASR 异常 | `run_in_executor` 包同步 SDK；建立后立即冒烟测试；mock 永远可用 |
| 小米推送审核需要 AppID/AppKey/AppSecret | 测试机审核 30min~1d | Sprint 4 默认 mock；真实 reg_id 申请放第一周并行 |
| MIUI 拦截录音权限 | 录音文件为空 | runtime permission 检查 + 用户引导；DEGRADED 时预警 |
| WS 单 worker 上限连接数（~1000） | 大租户超量 | MVP < 100 并发；Redis pub/sub 推到 v1.1 |
| 音频帧背压丢帧 | 转写漏字 | 5s 缓冲；丢帧时上报 DEGRADED；最终用本地完整录音重新分析作兜底 |
| JWT 在 WS query 上传输被日志记录 | 凭据泄漏 | 短期 token（15min）；uvicorn 关闭 query 入访问日志 |
| MiPush payload 上限 4KB | 业主信息超长截断 | DIAL_REQUEST 只带 ID + 脱敏号 + 姓名；详细信息 App 后续 GET 拉 |
| feedback 双订阅重复处理 | 反馈记两次 | suggestion_id 作 idempotency key |

---

## Section 11：任务派发顺序与依赖

### 任务依赖图

```
T1 (Alembic + 模型) ──┬──→ T2 (StreamingASR mock) ──┐
                     │                              │
                     ├──→ T4 (MiPush mock)         ├──→ T7 (WS 信令 + 广播)
                     │                              │       │
                     ├──→ T6 (PATCH /tag API)      │       ├──→ T8 (Android MiPush)
                     │                              │       ├──→ T9 (RealtimeCallActivity)
                     └──→ T3 (RealtimeLLM 引擎) ────┘       ├──→ T10 (AudioStreamClient)
                                                            ├──→ T11 (PostCallTagDialog)
                     T5 (DIAL_REQUEST API) ───────────────  ┤
                                                            ├──→ T13 (PC ws-client)
                                                            ├──→ T14 (RealtimeCallWorkstation)
                                                            └──→ T15 (PC AI 卡片 feedback)
                                                                    │
                                                                    ├──→ T12 (Android 降级逻辑)
                                                                    └──→ T16 (端到端集成测试)
```

### 模型分配（Subagent-Driven Development）

| 任务 | 模型 | 理由 |
|------|------|------|
| T1（Alembic + 模型字段） | haiku | schema 机械改动 |
| T2（StreamingASR backend） | sonnet | dispatcher + DashScope/mock 双实现 |
| T3（RealtimeLLM 引擎） | sonnet | 三种触发条件状态机 |
| T4（MiPush 客户端 + mock） | sonnet | HTTP 客户端 + mock 队列 |
| T5（DIAL_REQUEST API） | sonnet | 跨表查询 + 推送编排 |
| T6（PATCH /tag API） | haiku | 单表更新 + 鉴权 |
| T7（WS 信令 + 广播） | sonnet | ConnectionManager + 鉴权 + 协议解码 |
| T8（Android MiPush） | sonnet | SDK 集成 + Receiver |
| T9（RealtimeCallActivity） | sonnet | 完整四区 UI |
| T10（AudioStreamClient） | sonnet | 多线程 + WS + AudioRecord |
| T11（PostCallTagDialog） | sonnet | Dialog UI + 提交 |
| T12（Android 降级状态机） | sonnet | 状态切换 + 重连 |
| T13（PC ws-client） | sonnet | 重连/心跳/事件分发 |
| T14（PC RealtimeCallWorkstation） | sonnet | 三栏页面 + agent/observer 双形态 |
| T15（PC AI 卡片 feedback） | sonnet | 卡片栈 + 反馈 POST |
| T16（端到端集成测试） | sonnet | 跨多模块 |

### 两阶段评审（每任务）

```
implementer subagent → spec reviewer → code quality reviewer → 标记完成
```

任一阶段返回 NEEDS_CHANGES 则让 implementer 修复后重审。

---

## Section 12：验收标准

### 后端

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/python3.12 -m pytest --tb=short -q
```

预期：120+ tests，全部绿（Sprint 4 新增 ~16 个测试）。

### 前端

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx tsc --noEmit && npm run build
```

预期：clean build，无 TypeScript 错误。

### Android

```bash
cd /Users/shuo/AI/autoluyin/poc/android
./gradlew test
```

预期：单元测试全绿。

### 端到端冒烟（手动）

1. 启动后端（mock 三个 backend）
2. 启动前端 `npm run dev`
3. PC 登录 admin → 创建 case → 分配给 agent
4. PC 登录 agent → 案件列表点「拨打」
5. Android（mock MiPush 直接调本地接收方法）→ 弹 RealtimeCallActivity
6. PC 工作台自动弹出 → 显示 ASR mock 文本流 + AI 卡片
7. Android 点挂断 → 弹 PostCallTagDialog → 提交 → 跳回任务列表
8. PC 跳到 `/calls/{call_id}` 看完整记录

---

## 关键约束（继续遵循 Sprint 0-3b 已定规则）

- 手机号一律 plaintext 上行 / AES-256 存储 / 脱敏输出
- API 路径统一 `/api/v1/`
- 错误响应 `{"code": "ERR_XXX", "message": "..."}`
- 前端禁止 `any`，必须类型完整
- Android 禁止主线程网络
- 所有 DB 查询带 `tenant_id`
