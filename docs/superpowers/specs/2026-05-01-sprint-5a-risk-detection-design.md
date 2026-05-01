# Sprint 5a 设计文档 — 实时风控（关键词 + LLM）与 L1/L2 处置

## 目标

在 Sprint 4 已交付的「实时 ASR + LLM 话术卡片」之上，注入**实时风控分支**：把每段确认型 ASR 文本同时送入「关键词匹配引擎 + LLM 风控判别器」，命中后通过 WebSocket 把风控事件广播到催收员 App + 督导 PC，并按 PRD §12 完成 L1/L2 处置闭环。

**核心 KPI**：

- 风控事件首次广播延迟 ≤ 1s（关键词命中 P90）/ ≤ 3s（LLM 命中 P90）
- 关键词词典热更新延迟 ≤ 60s
- LLM 风控召回 ≥ 0.9（在标注集上）

**不在 Sprint 5a 范围内（→ Sprint 5b）**：

- L3 强制挂断 + 租户级 L3 启用开关
- 60s 内 L2 未处置自动升级到 L3
- 通话后音频切片（±30s）+ 督导点击跳转录音播放
- 多 worker 风控广播（v1.1，与 Sprint 4 同步推后）

---

## 架构概览

### 端到端时序

```
Android (催收员)        后端 (FastAPI)              PC (督导)
 │                          │                          │
 │ 1. WS /ws/calls/{id}     │ 0. WS /ws/supervisor     │
 │    ?role=agent           │◄─────────────────────────┤
 ├─────────────────────────►│   ?token=<jwt>           │
 │                          │   (订阅本租户全部告警)   │
 │ 2. binary PCM            │                          │
 ├─────────────────────────►│                          │
 │                          │ 3. ASR utterance final   │
 │                          │      ↓                   │
 │                          │   ┌───────────┐          │
 │                          │   │ Keyword   │ 同步     │
 │                          │   │ matcher   │ <50ms    │
 │                          │   └─────┬─────┘          │
 │                          │         │ hit?           │
 │                          │         ↓                │
 │                          │   ┌───────────┐          │
 │                          │   │  Risk     │ 异步     │
 │                          │   │  detector │ 1-3s     │
 │                          │   │  (LLM)    │          │
 │                          │   └─────┬─────┘          │
 │                          │         │                │
 │ 4. {risk.event}          │         │                │
 │◄─────────────────────────┼─────────┤                │
 │                          │         │ broadcast      │
 │                          │         ├─────────────────►
 │                          │                          │ 5. {supervisor.alert}
 │                          │                          │
 │ 6. UI 处置：             │                          │ 7. AlertNotificationCenter
 │    L1 → Toast            │                          │    展示告警 + 跳通话详情
 │    L2 owner_threat       │                          │
 │      → 红 Banner（非阻塞）│                          │
 │    L2 agent_violation    │                          │
 │      → 全屏 Modal + 静音 │                          │
```

### 关键架构选择

| 项 | 选择 | 理由 |
|----|------|------|
| 关键词匹配引擎 | `pyahocorasick`（Aho-Corasick 自动机） | O(n + 命中数) 多模式同时扫描，预编译一次，<5ms 匹配 |
| 词典存储 | PostgreSQL `risk_keyword` 表 + 进程内 LRU + 60s TTL | 平台预置 + 租户私有，无需 Redis |
| LLM 风控触发 | 关键词命中 → 异步触发 LLM 二次判别（False Positive 过滤）+ utterance-final → 异步 LLM 自由判别 | 关键词召回高、LLM 兜底未在词典里的新表达 |
| LLM 模型 | DeepSeek `deepseek-chat`（与 Sprint 3b/4 复用）+ JSON-mode | 已有连接，零新依赖 |
| Speaker 来源 | DashScope `speaker_id`（近场=agent / 远场=customer） | Sprint 4 已实现；近场/远场双端听感识别准确率约 80%-85% |
| Speaker = unknown 处理 | 跳过风控（既不送词典也不送 LLM） | 避免误伤；speaker 漂移率会被监控指标记录 |
| 督导通道 | 新增 `/ws/supervisor` WS 端点（按租户广播） | 与 `/ws/calls/{id}` 解耦，督导单连接订阅本租户所有告警 |
| 阻塞 Modal 范围 | 仅 `agent_violation` 触发全屏 Modal + 静音麦克风 | 与 PRD §12.2 修订一致：催收员侮辱/威胁业主才阻塞；业主辱骂由催收员自主判断 |
| 词典管理入口 | 平台超管管理「平台预置词典」；租户管理员管理「租户私有词典」 | PRD §16 新增 `RiskKeyword.tenant_id NULL=平台预置` 双层结构 |
| 离线 / 历史回放 | 不计算风控（实时性是 Sprint 5a 核心） | 简化范围，未来可用 ETL 回填 |

---

## 数据模型

### 新增表 `risk_keyword`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL PK |  |
| tenant_id | BIGINT NULL | NULL=平台预置；非 NULL=租户私有 |
| category | VARCHAR(32) | `owner_abuse` / `owner_threat` / `agent_violation` / `agent_minor_misconduct` |
| speaker | VARCHAR(16) | `agent` / `customer`（必须，决定匹配维度）|
| level | VARCHAR(8) | `L1` / `L2`（Sprint 5a 仅这两档；L3 留给 5b） |
| keyword | VARCHAR(64) | UNIQUE(tenant_id, category, keyword) — 同租户同类别不允许重复 |
| is_active | BOOLEAN DEFAULT TRUE |  |
| created_at / updated_at | TIMESTAMP |  |

**初始数据（迁移内 seed，tenant_id = NULL 平台预置）：**

```python
# Alembic 5a-001 内嵌 seed
seed = [
    # owner_abuse — 业主辱骂催收员（L1 提示）
    ("owner_abuse",  "customer", "L1", "你妈"),
    ("owner_abuse",  "customer", "L1", "滚"),
    ("owner_abuse",  "customer", "L1", "傻逼"),
    ("owner_abuse",  "customer", "L1", "神经病"),
    ("owner_abuse",  "customer", "L1", "脑残"),
    # owner_threat — 业主威胁投诉（L2 红 Banner，非阻塞）
    ("owner_threat", "customer", "L2", "投诉"),
    ("owner_threat", "customer", "L2", "12345"),
    ("owner_threat", "customer", "L2", "上法院"),
    ("owner_threat", "customer", "L2", "媒体"),
    ("owner_threat", "customer", "L2", "律师"),
    ("owner_threat", "customer", "L2", "曝光"),
    # agent_violation — 催收员违规（L2 阻塞 Modal + 静音）
    ("agent_violation", "agent", "L2", "你妈"),
    ("agent_violation", "agent", "L2", "傻逼"),
    ("agent_violation", "agent", "L2", "再不还"),
    ("agent_violation", "agent", "L2", "黑名单"),
    ("agent_violation", "agent", "L2", "找你单位"),
    ("agent_violation", "agent", "L2", "找你家人"),
    # agent_minor_misconduct — 催收员小过（L1 仅记录 + Toast）
    ("agent_minor_misconduct", "agent", "L1", "随便你"),
    ("agent_minor_misconduct", "agent", "L1", "爱交不交"),
    ("agent_minor_misconduct", "agent", "L1", "给你减免"),
]
```

**索引：**

- `idx_riskkw_tenant_cat_speaker_active(tenant_id, category, speaker, is_active)` — 加载词典时按 `(tenant_id IS NULL OR tenant_id = :t) AND is_active = TRUE` 过滤

### 复用现有表

- `analysis_result.key_segments` JSON 增加 `"risks": [...]` 数组（沿用 Sprint 4 已有模式）
  ```json
  {
    "risks": [
      {
        "id": "uuid",
        "category": "agent_violation",
        "speaker": "agent",
        "level": "L2",
        "trigger": "keyword",          // "keyword" | "llm" | "keyword+llm"
        "matched_keyword": "你妈",
        "llm_confidence": 0.95,        // 仅 LLM 确认时存在
        "transcript_text": "你妈的再不还钱",
        "ts_ms": 12450,
        "raised_at": "2026-05-01T10:23:11Z",
        "agent_action": null,           // 5a 占位，5b 回写
        "supervisor_action": null       // 5a 占位，5b 回写
      }
    ]
  }
  ```
  > 注：`agent_action` / `supervisor_action` 在 Sprint 5a 落库时一律为 `null`，留给 Sprint 5b 引入回写 API。

### Alembic 迁移

`alembic/versions/5a_001_risk_keyword.py`：建表 + seed + 索引；幂等。

---

## 后端模块

### 目录结构

```
poc/backend/app/risk/
├── __init__.py
├── keyword_matcher.py    # AC 自动机封装 + 词典加载
├── risk_detector.py      # 关键词匹配 + LLM 调度的协调器
├── risk_analyzer.py      # LLM 调用（DeepSeek）+ JSON-mode prompt
└── supervisor_manager.py # /ws/supervisor 连接池 + 按租户广播
```

### `keyword_matcher.py`

```python
class RiskKeywordMatcher:
    """单实例 per (tenant_id, speaker)，预编译 AC 自动机。
    内部 LRU + 60s TTL；过期自动重新从 DB 加载。
    """
    def __init__(self, tenant_id: int, speaker: str):
        self.tenant_id = tenant_id
        self.speaker = speaker  # "agent" | "customer"
        self._automaton: ahocorasick.Automaton | None = None
        self._loaded_at: float = 0.0
        self._kw_meta: dict[str, dict] = {}  # keyword → {category, level, keyword_id}

    async def ensure_loaded(self, db: AsyncSession) -> None: ...
    def match(self, text: str) -> list[KeywordHit]: ...

@dataclass
class KeywordHit:
    keyword: str
    category: str
    level: str
    keyword_id: int
    span: tuple[int, int]
```

**全局单例缓存**：`_matchers: dict[(tenant_id, speaker), RiskKeywordMatcher]`，按 (tenant_id, speaker) 复用。

### `risk_detector.py`

```python
class RiskDetector:
    """每 CallSession 一个实例，负责：
    1) 收到 utterance final → 决定 speaker
    2) speaker == 'unknown' → 跳过
    3) 关键词同步匹配 → 命中 → 立即 emit + 异步 LLM 二次判别
    4) 关键词未命中时，按节流策略调 LLM 自由判别（捕捉新表达）
       节流：每个 (call_id, speaker) 维度，至少间隔 10s 才调一次自由判别
    5) emit 时去重（同一 transcript_text 的同一 category 60s 内只 emit 一次）
    """
    def __init__(self, call_id: int, tenant_id: int, on_event: Callable):
        ...

    async def on_utterance(self, utt: UtteranceFinal, db: AsyncSession) -> None: ...
```

**触发时机**：在 `CallSession.on_asr_final()` 里，紧挨着 LLM 话术卡片调度并行启动。

### `risk_analyzer.py`

```python
async def analyze_risk_with_llm(
    transcript_text: str,
    speaker: str,
    keyword_hint: KeywordHit | None,
) -> LLMRiskVerdict:
    """调用 DeepSeek JSON-mode：
    输入：utterance 文本 + speaker + 关键词命中提示（可空）
    输出：{
      "is_risk": bool,
      "category": "owner_abuse|owner_threat|agent_violation|agent_minor_misconduct|none",
      "level": "L1|L2|none",
      "confidence": 0.0-1.0,
      "reason": "短解释"
    }
    """

@dataclass
class LLMRiskVerdict:
    is_risk: bool
    category: str
    level: str
    confidence: float
    reason: str
```

**Prompt 要点**：

- 给 4 个 category 的中文定义 + 各 1-2 个范例
- 明确「业主辱骂催收员」(owner_abuse) ≠「催收员辱骂业主」(agent_violation)
- speaker 字段是输入，不是 LLM 推断
- `confidence < 0.7` 视为不命中，丢弃
- 与关键词命中冲突时（关键词说有、LLM 说无），以 `confidence > 0.85` 为门槛覆盖关键词

**降级**：mock 实现走 keyword-only（无 LLM），用于本地开发与单元测试。

### `supervisor_manager.py`

```python
class SupervisorManager:
    """tenant_id → set[WebSocket]"""
    async def connect(self, tenant_id: int, ws: WebSocket): ...
    async def disconnect(self, tenant_id: int, ws: WebSocket): ...
    async def broadcast(self, tenant_id: int, event: dict): ...
```

进程内单例，与 Sprint 4 的 `ConnectionManager` 同样模式（无 Redis）。

### 新增 WebSocket 端点

`/ws/supervisor?token=<jwt>`：

- 鉴权：JWT → user_id；要求 `role in {supervisor, admin}`
- 订阅：自动按 user.tenant_id 加入租户广播组
- 服务端 → 客户端：`{type: "supervisor.alert", call_id, ...event}`
- 客户端 → 服务端：暂无（5a 不做督导操作回写，留给 5b 的强制挂断）

### 新增 HTTP 端点（admin 词典管理）

| Method | Path | 角色 | 说明 |
|--------|------|------|------|
| GET | `/api/v1/admin/risk-keywords` | platform_super / tenant_admin | 列表，按 category/speaker/level 过滤 |
| POST | `/api/v1/admin/risk-keywords` | 同上 | 新增；platform_super 可设 tenant_id=NULL |
| PATCH | `/api/v1/admin/risk-keywords/{id}` | 同上 | 编辑/启用停用 |
| DELETE | `/api/v1/admin/risk-keywords/{id}` | 同上 | 软删除 → `is_active=False` |

**租户隔离**：tenant_admin 只能操作 `tenant_id = self.tenant_id`；platform_super 可操作 `tenant_id IS NULL` 与所有租户。

---

## WebSocket 协议

### `/ws/calls/{call_id}` 新增 server→client 消息

```json
{
  "type": "risk.event",
  "id": "uuid",
  "category": "agent_violation",
  "speaker": "agent",
  "level": "L2",
  "trigger": "keyword+llm",
  "matched_keyword": "你妈",
  "llm_confidence": 0.95,
  "transcript_text": "你妈的再不还钱",
  "ts_ms": 12450,
  "raised_at": "2026-05-01T10:23:11.123Z"
}
```

### `/ws/supervisor` server→client 消息

```json
{
  "type": "supervisor.alert",
  "call_id": 123,
  "case_id": 456,
  "agent_user_id": 789,
  "agent_name": "张三",
  "callee_phone_masked": "138****1234",
  "risk": {
    "id": "uuid",
    "category": "owner_threat",
    "level": "L2",
    "trigger": "keyword",
    "matched_keyword": "投诉",
    "transcript_text": "我去 12345 投诉你们",
    "ts_ms": 12450,
    "raised_at": "2026-05-01T10:23:11.123Z"
  }
}
```

---

## Android 端（催收员 App）

### 新增模块

```
android/app/src/main/java/com/autoluyin/risk/
├── RiskAlertController.kt    # 路由 + UI 状态机
├── RiskBannerView.kt         # owner_threat 红 Banner
└── RiskBlockingModal.kt      # agent_violation 全屏 Modal
```

### 路由规则（`RiskAlertController.kt`）

```kotlin
fun onRiskEvent(event: RiskEvent) {
    val isDoubleConfirmed = event.trigger == "keyword+llm" &&
                            (event.llmConfidence ?: 0.0) > 0.85
    when {
        event.level == "L1" -> showToast(...)   // owner_abuse / agent_minor_misconduct 同款 Toast
        event.category == "agent_violation" && isDoubleConfirmed -> {
            muteMicrophone()
            showBlockingModal(onDismiss = { unmuteMicrophone() })
        }
        event.level == "L2" -> showRedBanner(dismissible = true)  // owner_threat 与未双确认的 agent_violation 都走这条
        else -> Log.w(TAG, "Unknown risk: $event")
    }
}
```

**关键约束**：

- `agent_violation` Modal **只能由催收员主动点击「我已知晓」关闭**（强制反思动作）
- Banner / Modal 内容：matched_keyword 高亮 + transcript_text + 简短指引文案
- 同一 risk.id 重复收到 → 忽略（前端去重）
- 双确认门槛 `confidence > 0.85` 写在 `RiskAlertController` 而非后端：后端 emit 全量 risk.event，前端按业务策略路由，便于后续策略调整不动 Wire 协议

### 与 Sprint 4 现有 UI 的关系

- 不影响话术卡片浮动按钮
- Modal 出现期间，话术卡片仍可见但不可点击（覆盖层在话术卡片之上）

---

## PC 前端

### 督导端（新增）

- `/supervisor/alerts` 页面：
  - 顶部 `AlertNotificationCenter`（铃铛 + 未处置计数）
  - 列表：实时滚动，每条告警显示 `{催收员姓名 / 业主电话 / category 标签 / matched_keyword / 触发时间 / [跳通话详情] 按钮}`
  - 点击跳转：现有 `/admin/calls/{id}` 详情页（5b 再加录音点击跳转）
- 全局 `useSupervisorAlerts()` hook：在 `<App>` 顶层订阅 `/ws/supervisor`，把告警注入 Zustand store
- 告警列表只在客户端缓存（不持久化），刷新页面重连后从空开始；历史可在通话详情页 `analysis.key_segments.risks` 看到

### 催收员工作站（仅微调）

- 通话详情页 `transcript` 区域，命中关键词的句子下方显示 inline 风控注释
  ```
  [10:23:11] 业主：我去 12345 投诉你们
            ⚠ 业主威胁（L2 owner_threat · 关键词 "投诉"）
  ```

### 平台超管 / 租户管理员（新增）

- `/admin/risk-keywords` 页面：
  - 表格：keyword / category / speaker / level / tenant_id（NULL=平台预置）/ is_active / 操作
  - 新增 / 编辑 Modal：4 个枚举字段下拉，keyword 文本框
  - tenant_admin 只看到本租户 + 平台预置（只读）；platform_super 看到全部 + 可编辑平台预置

---

## 测试策略

### 后端（pytest，新增 ~16 个）

| 文件 | 测试 | 数量 |
|------|------|------|
| `tests/risk/test_keyword_matcher.py` | AC 命中 / 多关键词同句 / 大小写不敏感 / 60s TTL 过期重载 / tenant 私有词覆盖平台 | 5 |
| `tests/risk/test_risk_detector.py` | 关键词命中→emit 事件 / speaker=unknown 跳过 / 60s 去重 / LLM 否决关键词（高 confidence）/ LLM 单独命中（无关键词）| 5 |
| `tests/risk/test_risk_analyzer.py` | mock LLM JSON-mode 返回正确解析 / confidence<0.7 丢弃 / mock 模式纯 keyword | 3 |
| `tests/api/test_supervisor_ws.py` | 鉴权失败 / 订阅本租户告警 / 跨租户隔离 | 3 |
| `tests/api/test_admin_risk_keywords.py` | 列表过滤 / tenant_admin 不能改平台预置 / platform_super 全权 / 软删除 | 4 |

### 前端（vitest + RTL，新增 ~3 个）

- `useSupervisorAlerts.test.tsx` — WS 收到事件 → store 更新
- `AlertNotificationCenter.test.tsx` — 渲染未处置计数 + 跳转
- `RiskKeywordsTable.test.tsx` — 角色权限差异

### Android（JUnit5 + MockK，新增 1 个）

- `RiskAlertControllerTest` — 4 种 (level, category) 组合的路由正确性 + 同 risk.id 去重

### 集成测试

- 已有 Sprint 4 的 `tests/integration/test_call_flow.py`：补一条用例「ASR 输出含 '你妈' → /ws/calls 收到 risk.event + /ws/supervisor 收到 supervisor.alert」

**总测试数目标**：pytest ≥ 145（Sprint 4 末为 ~129），vitest ≥ 7（Sprint 4 末为 ~4）。

---

## 性能与监控

| 指标 | 目标 | 监控点 |
|------|------|--------|
| 关键词匹配 P90 | < 5ms | `risk_keyword_match_ms` histogram |
| 关键词→广播 P90 | < 1s | `risk_event_emit_ms` histogram |
| LLM 风控 P90 | < 3s | `risk_llm_ms` histogram |
| LLM 调用失败率 | < 1% | `risk_llm_error_total` counter |
| Speaker=unknown 率 | < 15% | `risk_skipped_unknown_speaker_total` counter |
| 词典热更新延迟 | < 60s | TTL 固定，无需独立指标 |

监控落点：复用 Sprint 4 的 Prometheus exporter（`/metrics`），新增上述 5 个指标。

---

## 风险与取舍

### Speaker 误判

- DashScope 近场/远场基于声纹特征，约 15-20% 误判率
- **5a 不做投票/平滑**（避免延迟），speaker=unknown 直接跳过；监控 unknown 率，> 15% 触发告警
- 5b 可考虑滑动窗口投票

### LLM 假阳性

- DeepSeek 对短文本风控判断存在过度谨慎倾向（"麻烦"被判 owner_threat）
- **门槛**：`confidence < 0.7` 丢弃；与关键词冲突时需 `confidence > 0.85` 才能覆盖
- 上线后用人工标注集回归（5a 验收前 ≥ 50 条，覆盖 4 个 category × 2 speaker）

### 词典更新延迟

- 60s TTL：管理员添加词后最长 60s 才能被新通话生效
- **5a 不做主动 invalidate**（多 worker 复杂度高）；如果未来产生强需求，5b 考虑 Postgres LISTEN/NOTIFY

### 阻塞 Modal 滥用

- 若 `agent_violation` 误报率高，催收员体验受损
- **缓解**：只在 `trigger == "keyword+llm"` 且 `confidence > 0.85` 时阻塞；单独关键词命中或单独 LLM 命中只发 `risk.event`，前端走 owner_threat 同款红 Banner（不阻塞）。这把"高 FP 风险路径"全部归口到非阻塞 Banner，阻塞 Modal 仅在双确认时触发
- 申诉/反阻塞流程留给 Sprint 5b（与回写 API、督导审核一并设计）

### 多 worker 广播

- 当前进程内 `SupervisorManager` 仅在单 worker 下正确
- **Sprint 5a 与 Sprint 4 一并接受单 worker 限制**；5b 或独立的「实时广播 v1.1」 sprint 引入 Redis pub/sub 一并升级

---

## 验收

### 端到端 Demo

1. 业主侧说「我去 12345 投诉你们」 → 5s 内：
   - 催收员 App 红 Banner 出现，文案含 "投诉"
   - 督导 PC `/supervisor/alerts` 出现 supervisor.alert 行
   - 通话详情页 transcript 段落下出现 inline 注释
2. 催收员说「再不还钱给你拉黑名单」 → 5s 内：
   - 催收员 App 全屏 Modal，麦克风静音指示灯亮
   - 督导 PC 出现告警
   - Modal 关闭后麦克风自动恢复
3. 业主说「滚」 → 催收员 App Toast，督导 PC 出现告警，无阻塞
4. 平台超管在 `/admin/risk-keywords` 添加新关键词「举报」(owner_threat L2 customer) → 1 分钟后新通话触发该词命中

### 量化目标

- pytest ≥ 145 全绿
- vitest ≥ 7 全绿
- Android `./gradlew assembleDebug` 绿
- 标注集（≥ 50 条）召回 ≥ 0.9 / 精确 ≥ 0.85

---

## 与 PRD 对齐

- **PRD §12.2 / §12.3** — 风控四象限定义（owner_abuse / owner_threat / agent_violation / agent_minor_misconduct）已落地代码
- **PRD §16** — `RiskKeyword` 数据模型已落地
- **PRD §19** — MVP 范围内「实时风控 L1/L2」交付（L3 推到 5b）

---

## 与 Sprint 4 / 5b 的边界

| 功能 | Sprint 4 | Sprint 5a | Sprint 5b |
|------|---------|-----------|-----------|
| 实时 ASR + 话术卡片 | ✅ | — | — |
| 关键词风控 L1/L2 | — | ✅ | — |
| LLM 风控 | — | ✅ | — |
| 督导实时告警通道 | — | ✅ | — |
| 风控词典 admin CRUD | — | ✅ | — |
| L3 强制挂断 | — | — | ✅ |
| 60s L2→L3 升级 | — | — | ✅ |
| 通话后音频切片 ±30s | — | — | ✅ |
| 督导点击跳转录音播放 | — | — | ✅ |
| 多 worker 广播 (Redis) | — | — | v1.1 |
