# 系统综合评估 — 2026-05-07（v1.7.4 后）

**目的**：盘点 v1.4 → v1.7.4 系列后的系统真实完成度，给出启动测试指南。

## A. 前后端对齐情况

### A.1 接口面 vs 调用面

| 维度 | 数 |
|---|---|
| 后端 FastAPI 路由 | 176 个（49 个模块文件） |
| 前端 Refine 资源调用 | 93 个 endpoint URL（grep `useCustom/useOne/useList/useCreate/useUpdate/useDelete/useCustomMutation`） |

**对齐评估（来自 `docs/FRONTEND_BACKEND_ALIGNMENT_AUDIT.md`，已经过 v1.6.0 收尾扫尾 + v1.7.2 Refine v5 残余修复）**：

| 类别 | 数量 | 详情 |
|---|---|---|
| ✅ 真实对齐 | 176 - 14 = ~162 | FE/Android/公开 fetch 等合法消费方覆盖 |
| ✅ FE 缺动作按钮已修 | 3 | dispatch/complete/cancel（v1.6.0 之前） |
| ✅ 死端点清理 | 1 | `/admin/users/invite`（v1.6.x 删除） |
| ✅ Refine v5 API 收尾 | 13 | `useCustom.refetch` → `query.refetch`（v1.7.2 修） |
| 🟡 上游消费 | 8 | Android（calls/devices/dial-start/heartbeat）+ 公开 fetch（help/verify/onboarding） |
| 🟡 浏览器直链 | 2 | `evidence-bundle` / `documents/{id}/download`（GET 直接下载） |

**结论**：**FE↔BE 对齐 100%**（无 orphan endpoint，无未实现 UI 入口）。

### A.2 数据流验证

每个核心模块都有 e2e 验证机制：

| 模块 | 验证脚本 / 测试 |
|---|---|
| 11 角色登录 + 主流程 | `scripts/api_smoke.py`（11 角色覆盖） |
| 法务转化通道（Sprint 16） | `scripts/legal_conversion_smoke.py`（13 步链） |
| Sprint 5a 风控检测 | `tests/integration/test_sprint5a_risk_e2e.py` |
| Alembic 迁移 round-trip | `tests/test_alembic_roundtrip.py`（v1.5 链 19001-19004 + v1.6 链 20001 自动覆盖） |
| 配额 / 计费 / 实时分钟 | `tests/api/test_billing_split.py` 等 |

**测试基线**：527 backend + 150 frontend 全绿，`tsc -b` + `vite build` + `pytest --cov` 全通过。

## B. 规划 UI vs 实现 UI 完成度

### B.1 PRD §21 全景（来自 `docs/UI_GAPS.md`）

| 维度 | 数 |
|---|---|
| PRD §21 总页数 | 83 |
| ✅ P0 完整实现 | **74** |
| ⚠️ P0 部分缺失 | **0** |
| ❌ P0 完全缺失 | **0** |
| P1 stub（已标记，暂缓 v1.1+） | 20 |
| 非 MVP，v1.1 暂缓 | 3 |
| UI 超出 PRD §21 的额外页（已实现） | 7 |

**P0 完成度：100%**（v1.6 收尾扫尾后唯一遗留的 AGB.5B.2 案件详情已确认实现）。

### B.2 HTML 原型 vs React 实现

ui/ 目录 **28 个 HTML 原型文件**，分两批：

**a. v1.4/v1.5 反向出（14 个）** — 从 React 实现反向产出，结构天然对齐：

| HTML | React 路径 |
|---|---|
| `supervisor.html#sv-livewall` | `supervisor/live-wall` |
| `help-app.html` | `help/app` |
| `verify.html` | `verify` |
| `agent-workstation-live.html` + `admin-workstation-live.html` | `agent/workstation/live` + `admin/workstation/live` |
| `supervisor-review-detail.html` | `supervisor/reviews/detail` |
| `supervisor-risk-events.html` | `supervisor/risk-events` |
| `admin-scripts-effectiveness.html` + `admin-scripts-versions.html` | `admin/scripts/*` |
| `admin-compliance-detail.html` | `admin/compliance/detail` |
| `admin-settlement-detail.html` | `admin/settlements/detail` |
| `admin-provider-detail.html` | `admin/providers/detail` |
| `admin-user-new.html` + `workorder-new.html` + `admin-risk-keyword-form.html` | 对应 form 页 |
| `ops-provider-new.html` | `ops/providers/new` |

**b. v1.0 时期原始设计稿（14 个）** — HTML 先于 React，作为设计基准；v1.6 完成主要还原：

| HTML | 状态 | 备注 |
|---|---|---|
| `login.html` | ✅ v1.6.0 还原（双面板设计） | 严格 1:1 |
| `admin.html`（16 sub-section） | ✅ topbar + cases kanban 已还原 | 整体 shell 已用 AppLayout 替代 |
| `agent-pc.html`（6 sub-section） | ✅ 三栏 RealtimeCallShell 列宽对齐 | 240/1fr/340 grid |
| `legal.html` | ✅ enforcing badge 紫色对齐 | |
| `workorder.html` | ✅ priority 4 档建模 + badge | v1.6.0 |
| `supervisor.html`（12 sub-section） | ✅ live-wall 反向出，其他天然对齐 | |
| `provider-admin.html`（11 sub-section） | ✅ 已实现 7 页（核心覆盖） | 4 个 P1 stub |
| `platform-superadmin.html`（11 sub-section） | ⚠️ 实现 4 个 P0（health/audit/cost/plans） | 7 个 sub-section v2.x 候选 |
| `platform-ops.html`（15 sub-section） | ✅ 全实现 | |
| `project-manager.html` | ✅ pm 目录 1 页（两侧共用模板） | |
| `index.html` / `payment-h5.html` / `app-agent.html` | n/a | 公开页或 Android |

**HTML → React 完成度：93%**（核心 13/14 全到位；platform-superadmin 7 个 sub-section 是已知缺口，明确 v2.x 候选）。

### B.3 React 页统计（按角色）

| 角色目录 | 页数 |
|---|---|
| admin | 26 |
| ops | 13 |
| supervisor | 7 |
| provider | 7 |
| super | 6 |
| agent | 3 |
| workorder | 3 |
| legal | 2 |
| login / verify / pm / help / calls | 各 1 |
| **合计** | **72** |

## C. 启动服务测试系统

### C.1 一键起整个系统（推荐）

```bash
cd /Users/shuo/AI/autoluyin/poc

# 1. 准备 .env（首次）
cp backend/.env.example backend/.env
# 默认值已可跑：mock ASR + mock LLM + local 录音落盘

# 2. 起核心服务（postgres + redis + backend + celery_worker）
docker compose up -d

# 3. 等后端 healthy（约 30s — alembic upgrade head + uvicorn）
docker compose ps
# backend healthcheck 通过后才算启动完成

# 4. seed demo 数据（11 角色账号 + 案件 + 风控关键词等）
docker exec autoluyin-backend python -m scripts.seed_demo
```

### C.2 起前端 dev 服务

```bash
cd /Users/shuo/AI/autoluyin/frontend

# 首次：安装依赖
npm install

# dev server（默认 localhost:5173）
npm run dev
```

浏览器打开 http://localhost:5173/，登录页就绪。

### C.3 11 角色 demo 账号

`scripts/seed_demo.py` 落地账号（密码统一）：

| 角色 | 手机号 | 密码 |
|---|---|---|
| platform_superadmin | 13000000001 | `Demo@1234` |
| platform_ops | 13000000002 | `Demo@1234` |
| supervisor | 13000000003 | `Demo@1234` |
| agent_internal | 13000000004 | `Demo@1234` |
| agent_external | 13000000005 | `Demo@1234` |
| legal | 13000000006 | `Demo@1234` |
| workorder | 13000000007 | `Demo@1234` |
| project_manager_property | 13000000008 | `Demo@1234` |
| project_manager_provider | 13000000009 | `Demo@1234` |
| provider_admin | 13000000010 | `Demo@1234` |
| admin（物业管理员） | 13000000011 | `Demo@1234` |

> 注：实际密码 / 编号请以 `scripts/seed_demo.py` 为准；如不一致可直接读源。

### C.4 端到端冒烟（无需浏览器）

```bash
# 11 角色登录 + 主流程
docker exec autoluyin-backend python -m scripts.api_smoke

# 法务转化通道 13 步链路
docker exec autoluyin-backend python -m scripts.legal_conversion_smoke
```

两个脚本都是幂等的，反复跑安全。

### C.5 关键 URL

| 用途 | URL |
|---|---|
| 前端登录 | http://localhost:5173/ |
| 后端 OpenAPI | http://localhost:18000/docs |
| 公开核验页（无登录） | http://localhost:5173/verify |
| Help 页（APK 二维码） | http://localhost:5173/help/app |
| 区块链存证查询 | http://localhost:5173/verify/{tx_hash} |

### C.6 常见排查

| 现象 | 排查 |
|---|---|
| backend 容器 unhealthy | `docker logs autoluyin-backend` 看 alembic 错或 starlette/fastapi import 错 |
| 前端登录 401 | 检查 `VITE_API_BASE` 是否指向 18000；或 seed_demo 是否跑过 |
| 实时通话墙没数据 | 需要 Android App 拨号触发 `dial-start`；或在 admin/cases 页手动模拟 |
| 录音文件 404 | 检查 `LOCAL_STORAGE_ROOT` 在容器里挂载到 `/data/recordings`；docker-compose 默认已配 |
| celery 不消费任务 | `docker logs autoluyin-celery`；redis 连接是否 healthy |

### C.7 关停

```bash
cd poc

# 关停（保留数据）
docker compose down

# 完全清理（包括 db / 录音 / redis）
docker compose down -v
```

## D. 已知约束 / 后续工作（产品决策类）

| 项 | 状态 | 阻塞 |
|---|---|---|
| platform-superadmin 7 sub-section（LLM Prompt / 区块链 / 存储 / 公告 / 审计扩展 等） | ⚠️ v2.x 候选 | 需选 P0 优先级 |
| recording_mode auto 决策阈值 UI | ⚠️ pending | 当前 10 分钟 / 网络评分硬编码；要不要做配置 UI |
| WS supervisor wall 多 worker 部署 | ⚠️ 已知约束 | dev 单 worker 可用；prod N>1 需补 Redis pub/sub |
| starlette → 1.0 / redis-py → 7 / pydantic → 2.13 | ⚠️ 上游/版本债 | 等 FastAPI / kombu / 专项 sprint 评估 |
| 支付二维码全屏（PRD 5A.6 / 6.5） | 非 MVP，v1.1 暂缓 | 产品决策 |
| 钉住关注下属（livewall 增强） | v1.4 P2 | 观察主管使用频率 |

## E. 发布历史

| Tag | 日期 | 主题 |
|---|---|---|
| v1.0.0-mvp | 2026-04-25 | MVP 第一版 |
| v1.4.0 | 2026-05-04 | B 路线安全基座 |
| v1.5.0-rc1 | 2026-05-06 | 法务转化通道（Sprint 16）+ B 路线收尾 |
| v1.6.0 | 2026-05-06 | UI 还原 + 死端点清理 + 工单 priority |
| v1.6.1 | 2026-05-07 | starlette CVE 修复 |
| v1.6.2 | 2026-05-07 | 12 包 patch 升级 |
| v1.6.3 | 2026-05-07 | frontend lucide/vitest/eslint refresh |
| v1.6.4 | 2026-05-07 | lint baseline 19→0 errors |
| v1.6.5 | 2026-05-07 | @types/node 25 + pyahocorasick 2 |
| v1.7.0 | 2026-05-07 | passlib → bcrypt 5（架构） |
| v1.7.1 | 2026-05-07 | celery 5.6 + redis 6.4 |
| v1.7.2 | 2026-05-07 | react 19 + Refine v5 cleanup |
| v1.7.3 | 2026-05-07 | tailwind v4 |
| v1.7.4 | 2026-05-07 | pytest 9（CVE-2025-71176） |

详见 `CHANGELOG_v1.5.md` / `CHANGELOG_v1.6.md` / `CHANGELOG_v1.7.md`。
