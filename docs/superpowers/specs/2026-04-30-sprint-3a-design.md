# Sprint 3a 设计文档 — 基础设施 + 加密 + 通话上传

## 目标

为催收外呼系统打通「通话结束 → 录音上传 → 异步处理队列」的基础链路，同时完成 AES-256 手机号加密的全量落地。Sprint 3b 在此基础上叠加 ASR + LLM + Android + PC 前端。

**不在 Sprint 3a 范围内：** DashScope ASR 集成、Qwen-Plus LLM 集成、Android 通话录音、PC 前端页面（均属 Sprint 3b）。

---

## 架构概览

```
Android App
  └─ POST /api/v1/devices/register   ← 绑定设备
  └─ POST /api/v1/devices/self-check ← 健康检查
  └─ POST /api/v1/calls/upload       ← 上传录音（multipart）

Backend
  ├─ app/core/crypto.py              ← AES-256-GCM 工具函数
  ├─ app/models/device.py            ← DeviceProfile ORM
  ├─ app/api/devices_v1.py           ← /api/v1/devices/* 路由
  ├─ app/api/calls_v1.py             ← /api/v1/calls/* 路由
  └─ app/worker/
      ├─ celery_app.py               ← Celery 实例
      └─ tasks/call_pipeline.py      ← process_call task（3a 骨架）

Infrastructure
  ├─ Redis（Celery broker + backend）
  └─ MinIO（录音文件存储，PoC 已有）
```

---

## Section 1：AES-256 手机号加密

### 工具函数（`app/core/crypto.py`）

| 函数 | 签名 | 说明 |
|------|------|------|
| `encrypt_phone` | `(plain: str) → str` | AES-256-GCM，输出 `{iv_hex}.{tag_hex}.{ciphertext_b64}` |
| `decrypt_phone` | `(cipher: str) → str` | 还原明文 |
| `mask_phone` | `(cipher: str) → str` | 解密后脱敏为 `138****1234` |

**密钥：** 环境变量 `AUTOLUYIN_AES_KEY`（64 位 hex = 32 字节）。应用启动时校验长度，缺失则 Fatal Error。

**加密格式：** `{iv_hex}.{tag_hex}.{ciphertext_b64}`（GCM 模式含认证 tag，防篡改）。

### 迁移范围

所有写入手机号的地方改为 `encrypt_phone(plain)`：

| Model | 字段 |
|-------|------|
| `Tenant` | `admin_phone_enc` |
| `UserAccount` | `phone_enc` |
| `OwnerProfile` | `phone_enc` |
| `CallRecord` | `callee_phone_enc` |

所有 API 响应中的手机号统一走 `mask_phone()` 或 `decrypt_phone()`（按角色）：

| 角色 | 可见度 |
|------|--------|
| `admin` / `supervisor` / `agent_internal` | `decrypt_phone()` 明文 |
| `agent_external` | `mask_phone()` 脱敏 |
| `workorder` / 其他 | 不返回手机号字段 |

### Alembic 数据迁移

新增一条 data migration：读取每行现有 plaintext `phone_enc`，调用 `encrypt_phone()` 覆写。空值跳过。测试环境数据量小，全表更新可接受。

迁移可回滚：保存迁移前快照（`phone_enc_plaintext_backup` 临时列），回滚时还原。

---

## Section 2：设备注册与管理

### Model：`DeviceProfile`（新建 `app/models/device.py`）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BigInteger | PK | |
| `device_id` | Text | UNIQUE NOT NULL | Android 端 UUID |
| `user_id` | FK → user_account | NOT NULL | 绑定 Agent |
| `tenant_id` | FK → tenant | NOT NULL | 所属租户 |
| `brand` | Text | nullable | 设备品牌 |
| `model` | Text | nullable | 设备型号 |
| `os_version` | Text | nullable | Android 版本 |
| `last_check_at` | DateTime TZ | nullable | 最后健康检查时间 |
| `is_healthy` | Boolean | default False | 最近自检是否通过 |
| `created_at` | DateTime TZ | server_default | |

索引：`(tenant_id, user_id)`

### 接口（`app/api/devices_v1.py`，prefix `/api/v1/devices`）

**`POST /register`** — 需要 JWT（`agent_internal` 或 `agent_external`）
```
Request:  {device_id, brand?, model?, os_version?}
Response: {device_id, user_id, tenant_id, created_at}
逻辑:    UPSERT DeviceProfile ON CONFLICT(device_id) DO UPDATE brand/model/os_version
```

**`POST /self-check`** — 需要 JWT
```
Request:  {device_id, recording_dir_ok, recording_toggle_on, permissions_ok}
Response: {can_call: bool}
逻辑:    is_healthy = 三项全 True; UPDATE DeviceProfile; return {can_call: is_healthy}
```

**`GET /config`** — 需要 JWT
```
Query:    ?device_id=xxx
Response: {key: value, ...}
逻辑:    查 app_config 表，device 级覆盖 global 级（PoC 逻辑不变，迁移路径即可）
```

### Android 调用时序

```
App 启动
  1. POST /api/v1/auth/login          → 获取 JWT
  2. POST /api/v1/devices/register    → 绑定设备（upsert，每次启动调用）
  3. POST /api/v1/devices/self-check  → 检查权限
  4. can_call=true → 显示拨打按钮
     can_call=false → 显示「设备未就绪」提示
```

---

## Section 3：通话上传接口 + 配额检查

### 接口（`app/api/calls_v1.py`，prefix `/api/v1/calls`）

**`POST /upload`** — 需要 JWT（`agent_internal` 或 `agent_external`），multipart

```
Request fields:
  device_id      str       必填，已注册设备
  case_id        int       必填，关联案件
  callee_phone   str       必填，明文（后端加密存储）
  started_at     ISO8601   必填
  ended_at       ISO8601   必填
  duration_sec   int       必填，>= 1
  file           audio/*   必填，<100MB，格式 mp3/m4a/amr/wav/aac/ogg

Response: {call_id: int, status: "uploaded"}
```

**上传流程（后端）：**
```
1. 验证 device_id 已注册且属于当前 user（403 ERR_DEVICE_NOT_FOUND）
2. 验证 case_id 属于 tenant（404 ERR_NOT_FOUND）
3. 配额检查（见下）
4. encrypt_phone(callee_phone) → CallRecord.callee_phone_enc
5. 上传文件到 MinIO → object_key
6. INSERT CallRecord(status='uploaded')
7. INSERT RecordingFile(call_id, object_key, duration_sec, format)
8. celery: process_call.delay(call_id)
9. return {call_id, status='uploaded'}
```

### 配额检查逻辑

```python
# 当前年月使用量
usage = get_or_create_usage(tenant_id, year_month)
if usage.used_minutes + ceil(duration_sec / 60) > tenant.monthly_minute_quota:
    raise 403 ERR_QUOTA_EXCEEDED

# 上传成功后增量
usage.used_minutes += ceil(duration_sec / 60)
db.commit()
```

`TenantMinuteUsage` 不存在当月记录时自动 `INSERT`（初始 `used_minutes=0`）。`tenant.monthly_minute_quota` 为 `null` 时视为不限量，跳过配额检查。

### 其他接口

**`GET /`** — Agent 查自己的通话列表
```
Query:    ?case_id=N&page=1&page_size=20
Response: PaginatedResponse[CallListItem]
权限:    agent 只看自己的（caller_user_id == current_user）
         supervisor 看全租户
```

**`GET /{call_id}`** — 通话详情
```
Response: CallDetail（含 recording_url、transcript、analysis）
3a 阶段 transcript/analysis 均为 null，3b 填充
权限:    agent 只看自己的；supervisor/admin 看全租户
```

### CallRecord 状态机

```
uploaded → queued → processing → processed
                              ↘ failed（重试 3 次后）
```

---

## Section 4：Celery + Redis 基础设施

### 目录结构

```
poc/backend/app/worker/
├── __init__.py
├── celery_app.py           ← Celery 实例
└── tasks/
    ├── __init__.py
    └── call_pipeline.py    ← process_call task
```

### `celery_app.py`

```python
from celery import Celery
import os

celery_app = Celery(
    "autoluyin",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
)
```

### `process_call` task（Sprint 3a 骨架）

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_call(self, call_id: int) -> None:
    # Sprint 3a: 仅更新状态为 queued，验证 task 基础设施可用
    # Sprint 3b: 填充 ASR → LLM → Transcript + AnalysisResult
    with get_db_session() as db:
        call = db.get(CallRecord, call_id)
        if not call:
            return
        call.status = "queued"
        db.commit()
```

### docker-compose 新增服务

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"

celery_worker:
  build: ./poc/backend
  command: celery -A app.worker.celery_app worker --loglevel=info -Q default
  depends_on: [redis, db]
  environment:
    - REDIS_URL=redis://redis:6379/0
    - AUTOLUYIN_AES_KEY=${AUTOLUYIN_AES_KEY}
    - DATABASE_URL=${DATABASE_URL}
```

### 测试策略

- **单元测试：** `CELERY_TASK_ALWAYS_EAGER=True` — task 同步执行，无需真实 broker
- **集成测试：** `fakeredis` mock broker（无需 testcontainers Redis）
- **验收标准：** 上传录音后，CallRecord.status 从 `uploaded` 变为 `queued`（task 被调度）

---

## Alembic 迁移清单

| 迁移编号 | 内容 |
|---------|------|
| 3a-001 | 新增 `device_profile` 表 |
| 3a-002 | 加密所有现有 phone_enc 字段（data migration） |

---

## 测试覆盖要求

| 模块 | 目标 |
|------|------|
| `crypto.py` | encrypt → decrypt 往返；mask 格式正确；错误密钥 raises |
| 设备注册接口 | register upsert；self-check 返回 can_call；未注册设备上传被拒 |
| 通话上传接口 | 正常上传 → CallRecord 创建 + Celery 任务入队；配额超限 → 403；错误 device_id → 403 |
| 配额逻辑 | 首次使用自动创建 usage；超限拒绝；临界值（恰好等于配额）通过 |
| Celery task | EAGER 模式下 process_call 将 status 更新为 queued |

---

## 不在 Sprint 3a 范围

- DashScope ASR 集成（Sprint 3b）
- Qwen-Plus LLM 集成（Sprint 3b）
- Android 通话录音与自动上传（Sprint 3b）
- PC 前端页面（Sprint 3b）
- 实时 WebSocket 通话辅助（Sprint 4）
- 风控引擎（Sprint 4）
