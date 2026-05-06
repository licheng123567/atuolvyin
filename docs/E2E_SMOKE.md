# MVP 端到端冒烟清单

> 每次部署或合大 feature 前跑一遍。

## 前置

1. docker 起来：`cd poc && docker compose up -d`
2. 等容器 healthy（特别是 autoluyin-backend）：`docker ps --filter "name=autoluyin"`
3. 跑迁移：`docker exec autoluyin-backend alembic upgrade head`
4. 跑 seed：`docker exec autoluyin-backend python -m scripts.seed_demo`

seed 幂等，可重复跑。首次输出 `[created]`，再次输出 `[exists]`。

## 第一层：API 冒烟（自动化）

```bash
docker exec -e BACKEND_URL=http://localhost:8000 autoluyin-backend python -m scripts.api_smoke
```

期望：11 角色全 ✅，退出码 0。

### 测试矩阵（v1.0 候选）

| 角色 | 手机号 | 测试端点 |
|------|--------|---------|
| platform_super | 13000000000 | GET /api/v1/super/health/services |
| platform_ops | 13000000001 | GET /api/v1/ops/tenants?page=1 |
| admin | 13000000002 | GET /api/v1/admin/dashboard/stats |
| supervisor | 13000000003 | GET /api/v1/supervisor/reviews?only_pending=false |
| agent_internal | 13000000004 | GET /api/v1/calls/?page=1 |
| agent_external | 13000000005 | GET /api/v1/calls/?page=1 |
| legal | 13000000006 | GET /api/v1/legal/cases?page=1 |
| workorder | 13000000007 | GET /api/v1/workorders?page=1 |
| project_manager_property | 13000000008 | GET /api/v1/pm/dashboard/property |
| project_manager_provider | 13000000009 | GET /api/v1/pm/dashboard/provider |
| provider_admin | 13000000010 | GET /api/v1/provider/dashboard/stats |

> 注：platform_super 登录后 token 中 role=`platform_superadmin`（auth 逻辑：无 tenant membership 时默认该值）。

### 历史结果

| 日期 | 范围 | 结果 |
|------|------|------|
| 2026-05-05 | 6 角色 | 6/6 ✅（Sprint 6 hardening 首次跑通）|
| 2026-05-05（晚）| 11 角色 | **11/11 ✅**（批 3 完成 / MVP v1.0 候选）|

## 第二层：浏览器视觉验证（人工）

打开 `http://localhost:5173`（或 vite fallback 端口），密码统一 `Demo@123!`。

### 批 2A 已实现角色

| 角色 | 手机号 | 必看页面 | ✅ |
|------|--------|---------|-----|
| 平台超管 | 13000000000 | 运营后台 → 租户列表 + 系统管理 → 健康/审计/成本/套餐 | |
| 运营员 | 13000000001 | 租户列表 + 试用跟进 + 服务商管理 | |
| 物业管理员 | 13000000002 | 管理看板 KPI / 案件看板拖拽 / 公海管理 / 结算管理 | |
| 督导小李 | 13000000003 | 质检复核列表 + 通话详情打分 | |
| 内勤小张 | 13000000004 | 我的案件 + 实时通话风控 banner | |
| 外勤小王 | 13000000005 | 我的案件（手机号脱敏 138****1234）| |

### 批 3 新增角色

| 角色 | 手机号 | 必看页面 | ✅ |
|------|--------|---------|-----|
| 法务老周 | 13000000006 | /legal/cases 列表 + 详情切换阶段 | |
| 工单小赵 | 13000000007 | /workorder/orders 列表 + 新建工单 + 详情指派 | |
| 项目经理（物业）| 13000000008 | /pm/dashboard 物业侧 4 KPI | |
| 项目经理（服务商）| 13000000009 | /pm/dashboard 服务商侧 4 KPI | |
| 服务商管理员 | 13000000010 | /provider/dashboard + 合作租户 + 团队 + 收入结算 | |

## 已发现 bug（按 commit）

| Bug | 修复 commit | 备注 |
|-----|------------|------|
| 5180 端口 CORS 被拒 | `0fbb7e3` | 改 allow_origin_regex 支持任意 localhost 端口 |
| 登录后落静态占位页 | Sprint 6 | RoleHomeRedirect 按 role 路由 |
| 缺 AUTOLUYIN_AES_KEY 环境变量 | Sprint 6 | .env.example 加默认值 + 注释 |
| FastAPI 0.115.4 status=204 注解 | Sprint 5b | admin_scripts delete 加 response_class=Response |
| Android push_reg_id 注册被丢弃 | Sprint 12 | DeviceRegisterRequest 加 push_reg_id/push_provider 字段 |

## 已知遗留问题（v1.1 候选）

| # | 问题 | 优先级 |
|---|------|------|
| 1 | 前端 ~29 个 pre-existing TS 错误（admin/dashboard, ops/tenants, supervisor/reviews 等老页面 Refine v5 API 变更）| P1 |
| 2 | MiPush 真推送需小米开发者 AAR + 真 app_secret，目前 stub | P1 |
| 3 | WebSocket connected_clients 健康页固定显示 0（未实现计数器）| P2 |
| 4 | LLM 平均延迟健康页固定 0.0（未 instrument）| P2 |
| 5 | settlement payment_proof 走 URL 字符串，未对接 MinIO 直传 | P2 |
| 6 | 服务商搜索手机号需 11 位精确匹配（确定性 IV 加密决定）| P3 |
| 7 | Sidebar ICON_MAP 是 path-based 而非 nav.ts 的 icon string，新加菜单图标 fallback 到 Home（视觉降级，功能不影响）| P3 |
