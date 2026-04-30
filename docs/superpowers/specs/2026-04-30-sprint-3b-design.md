# Sprint 3b 设计文档 — ASR 转写 + LLM 分析 + PC 前端 + Android 迁移

## 目标

在 Sprint 3a 基础设施之上，打通完整的「录音上传 → 异步转写 → AI 分析 → 前端展示」链路。Android 坐席端完成 JWT 认证迁移，自动上传录音到 v1 接口。

**不在 Sprint 3b 范围内：** WebSocket 实时通话辅助、风控引擎、工单/法务流程前端（均属 Sprint 4）。

---

## 架构概览

```
Android App (agent_internal / agent_external)
  └─ POST /api/v1/calls/upload    ← JWT 认证，case_id 替换 task_id

Backend Worker (Celery)
  process_call task 扩展:
    下载录音 → DashScope ASR → INSERT Transcript
                             → Qwen-Plus LLM → INSERT AnalysisResult
                             → status = "processed"

Backend API (新增/扩展)
  GET /api/v1/admin/cases/{case_id}   ← 含通话时间线 + AI 摘要
  GET /api/v1/agent/cases/{case_id}   ← 四栏工作台数据源
  GET /api/v1/calls/{call_id}         ← 填充 transcript + analysis

PC Frontend (新增页面)
  /admin/cases/{id}   两栏案件详情（业主信息 | 活动时间线）
  /agent/cases/{id}   四栏工作台（案件列表 | 画像 | 转写 | AI 分析）
  /calls/{id}         通话详情（录音播放 + 完整转写 + AI 分析）
```

---

## Section 1：Storage 层扩展

### `get_bytes` 方法（`app/core/storage.py`）

| 类 | 实现方式 |
|----|---------|
| `StorageBackend`（ABC） | 新增抽象方法 `get_bytes(object_key: str) -> bytes` |
| `LocalFileStorage` | `open(local_path(object_key), "rb").read()` |
| `MinIOStorage` | `client.get_object(bucket, object_key).read()` |
| `OSSStorage` | `bucket.get_object(object_key).read()` |

Worker 调用 `get_bytes` → 写临时文件 → 传给 DashScope ASR → `finally` 块删除临时文件。

---

## Section 2：Celery Pipeline 扩展

### Alembic 3b-001

修复 `transcript.call_id` FK：原始迁移错误指向废弃的 `call_log` 表，需改为 `call_record.id`。

### `process_call` 完整流程

```
CallRecord.status 状态机:
  uploaded → queued → processing → processed
                                ↘ failed（重试 3 次后）

执行步骤:
① call.status = "queued"；db.commit()
② call.status = "processing"；db.commit()
③ storage.get_bytes(recording_file.object_key) → 写 tempfile
④ asr.transcribe(local_path=tempfile) → {full_text, segments}
   INSERT Transcript(call_id, full_text, segments, asr_model)
⑤ llm.extract("collection", {amount_owed, months_overdue}, full_text)
   → {intent, promise_date, excuse_category, compliance_disclosed,
      risk_keywords, confidence, needs_review, summary}
   INSERT AnalysisResult(call_id, summary, key_segments, followup_suggestion,
                         prompt_version, llm_model, needs_review)
⑥ call.status = "processed"；db.commit()
⑦ 任意步骤异常 → call.status = "failed"；db.commit()；self.retry()
```

**异常处理：**
- ASR 失败（网络/格式）→ `failed` + retry
- LLM 失败 → `failed` + retry（transcript 已写入，retry 时检查是否存在避免重复）
- 重试 3 次耗尽 → 最终 `failed`，不再 retry

**测试策略：**
- `CELERY_TASK_ALWAYS_EAGER=True` 同步执行
- `asr_backend=mock`、`llm_backend=mock` 避免真实 API 调用
- 验证：上传后 CallRecord.status = "processed"，Transcript + AnalysisResult 各 1 条

---

## Section 3：API 设计

### `GET /api/v1/admin/cases/{case_id}`

**权限：** `admin` / `supervisor` 看全租户；`agent_internal` / `agent_external` 无此端点。

**Response：**
```json
{
  "case": {
    "id": 1,
    "stage": "in_progress",
    "pool_type": "private",
    "amount_owed": "8420.00",
    "months_overdue": 7,
    "priority_score": 5
  },
  "owner": {
    "name": "张大伟",
    "phone_masked": "138****6621",
    "building": "3栋",
    "room": "1201",
    "tags": ["老业主", "多次承诺未缴"]
  },
  "calls": [
    {
      "id": 10,
      "started_at": "2026-04-28T14:32:00+08:00",
      "duration_sec": 222,
      "status": "processed",
      "transcript_preview": "业主称近期手头紧…",
      "result_tag": "excuse",
      "confidence": 0.87,
      "agent_name": "李小红"
    }
  ],
  "timeline_events": [
    {"type": "assigned", "ts": "2026-04-20T09:00:00+08:00", "actor": "管理员", "note": null}
  ]
}
```

`transcript_preview`：`Transcript.full_text` 前 100 字符，status != "processed" 时为 `null`。

### `GET /api/v1/agent/cases/{case_id}`

**权限：** agent 只看自己案件（`CollectionCase.assigned_to == current_user.id`）。

**Response：** 同上结构，手机号按角色：
- `agent_internal`：`phone` 字段返回 `decrypt_phone()`（明文，供拨号）
- `agent_external`：`phone_masked` 字段返回 `mask_phone()`（脱敏）

### `GET /api/v1/calls/{call_id}`（扩展）

Sprint 3a 时 `transcript`/`analysis`/`recording_url` 均为 `null`；Sprint 3b 填充：

```json
{
  "call_id": 10,
  "status": "processed",
  "transcript": {
    "full_text": "完整转写文本…",
    "segments": [{"start": 0.0, "end": 3.5, "text": "您好…", "speaker": "agent"}]
  },
  "analysis": {
    "summary": "业主推托，称老人看病花费大，月底缴费",
    "intent": "delay",
    "promise_date": "2026-04-30",
    "excuse_category": "financial_hardship",
    "compliance_disclosed": true,
    "risk_keywords": ["老人看病"],
    "confidence": 0.87,
    "needs_review": false
  },
  "recording_url": "https://minio/.../presigned?expires=900"
}
```

`recording_url` 为 presigned URL，TTL 15 分钟（LocalFileStorage 环境下返回内部路径）。

---

## Section 4：PC Frontend

### `/admin/cases/{id}` — 两栏案件详情

**布局：** `grid-template-columns: 340px 1fr`（沿用 `admin.html` `detail-grid`）

```
左栏（340px）
  业主信息卡：头像首字 + 姓名 + 房间号
  手机号（masked）+ 负责员工
  累计欠费金额（红色大字）
  债务明细表（月份 | 物业费 | 滞纳金 | 合计）
  业主标签（badge）
  操作按钮：发送缴费链接 / 创建工单 / 转交法务

右栏（1fr）
  活动时间线（垂直 spine + node）
  通话条目：
    - 时长 + 时间 + 坐席名
    - AI 摘要卡片：摘要文本 + result_tag badge + confidence
    - 底部链接：查看录音 → /calls/{id} | 完整 AI 分析 → /calls/{id}#analysis
  系统事件条目：分配、阶段变更（灰色 node）
```

### `/agent/cases/{id}` — 四栏工作台

**布局：** `grid-template-columns: 280px 240px 1fr 340px`（沿用 `agent-pc.html` `workstation-grid`）

```
col-cases（280px）
  当前坐席案件列表（搜索框 + 案件卡片）
  点击切换 case，URL 更新

col-profile（240px）
  业主画像：姓名 + 手机号（agent_internal 明文，agent_external 脱敏）
  欠费金额 + 月数
  标签

col-transcript（1fr）
  通话选择 tabs（多次通话切换）
  逐句转写：[HH:MM:SS] speaker: text
  status != "processed" 时显示「转写处理中…」占位

col-ai（340px）
  AI 分析卡片：
    intent badge + confidence 进度条
    summary 文本
    promise_date（如有）
    risk_keywords chips
    needs_review 提示（如为 true 显示警告）
```

### `/calls/{id}` — 通话详情页

```
顶部：返回链接 + 通话基本信息（时间/时长/坐席/状态）
中部：录音播放器（audio 标签，src = recording_url）
下部两栏：
  左：完整转写（逐句，可点击跳转播放进度）
  右：AI 分析展开（所有字段）
```

---

## Section 5：Android 迁移

### `Api.kt`

| 旧接口 | 新接口 |
|--------|--------|
| `/api/devices/self-check` | `/api/v1/devices/self-check` |
| `/api/tasks/today` | `/api/v1/agent/cases` |
| `/api/calls/upload` | `/api/v1/calls/upload` |

新增 OkHttp `AuthInterceptor`：每个请求自动附加 `Authorization: Bearer {token}`。

### `MainActivity.kt`

- 登录成功后将 JWT token 写入 `SharedPreferences("autoluyin_prefs", "jwt_token")`
- App 启动时读取 token；token 缺失时跳转登录 Dialog
- 登出时清除 token

### `CallWatcherService.kt`

- `matchAndUpload()` 改用 `case_id`（从 `GET /api/v1/agent/cases` 响应缓存中，按手机号匹配取 `case.id`）
- `agent_internal` 角色响应含 `phone` 明文字段，用于匹配录音文件名中的号码
- 上传 multipart 的 `case_id` 字段替换原有 `task_id`

---

## Alembic 迁移清单

| 迁移编号 | 内容 |
|---------|------|
| 3b-001 | 修复 `transcript.call_id` FK → `call_record.id` |

---

## 测试覆盖要求

| 模块 | 目标 |
|------|------|
| `storage.get_bytes` | Local 读文件；MinIO mock 下载 |
| `process_call` pipeline | mock ASR + mock LLM → status=processed, Transcript + AnalysisResult 各 1 条 |
| pipeline 异常 | ASR 失败 → status=failed；LLM 失败 → status=failed |
| idempotency | Transcript 已存在时 retry 不重复插入 |
| admin/cases/{id} API | 返回 calls 列表含 transcript_preview；无权限 403 |
| agent/cases/{id} API | agent_internal 返回明文 phone；agent_external 返回 masked |
| calls/{id} API | status=processed 时 transcript/analysis 非 null |
| Android | 单元测试：AuthInterceptor 附加 Bearer header；case_id 正确传递 |

---

## 不在 Sprint 3b 范围

- WebSocket 实时通话辅助（Sprint 4）
- 风控引擎（Sprint 4）
- 工单 / 法务流程前端（Sprint 4）
- Android UI 重构（Sprint 4）
