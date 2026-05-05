# MVP 端到端冒烟清单

> 每次部署或合大 feature 前跑一遍。

## 前置

1. docker 起来：`cd poc && docker compose up -d`
2. 等容器 healthy（特别是 autoluyin-backend）：`docker ps --filter "name=autoluyin"`
3. 跑 seed：`docker exec autoluyin-backend python -m scripts.seed_demo`

seed 幂等，可重复跑。首次输出 `[created]`，再次输出 `[exists]`。

## 第一层：API 冒烟（自动化）

```bash
docker exec -e BACKEND_URL=http://localhost:8000 autoluyin-backend python -m scripts.api_smoke
```

期望：6 角色全 ✅，退出码 0。

### 测试矩阵

| 角色 | 手机号 | 测试端点 |
|------|--------|---------|
| platform_super | 13000000000 | GET /api/v1/ops/tenants?page=1 |
| platform_ops | 13000000001 | GET /api/v1/ops/tenants?page=1 |
| admin | 13000000002 | GET /api/v1/admin/scripts?page=1 |
| supervisor | 13000000003 | GET /api/v1/supervisor/script-labels |
| agent_internal | 13000000004 | GET /api/v1/calls/?page=1 |
| agent_external | 13000000005 | GET /api/v1/calls/?page=1 |

> 注：platform_super 登录后 token 中 role=`platform_superadmin`（auth 逻辑：无 tenant membership 时默认该值），可通过 ops/tenants 的 `platform_superadmin` 角色检查。

### 2026-05-05 基线结果

```
通过: 6/6  ✅  (Sprint 6 hardening 首次跑通)
```

## 第二层：浏览器视觉验证（人工）

打开 `http://localhost:5173`（或 5174），密码统一 `Demo@123!`，逐角色登录。

| 角色 | 手机号 | 必看页面 | ✅ |
|------|--------|---------|-----|
| 平台超管 | 13000000000 | 运营后台 → 租户列表（Demo 物业可见）| |
| 运营员 | 13000000001 | 运营后台 → 租户列表（Demo 物业可见）| |
| 物业管理员 | 13000000002 | 管理后台 → 话术库（共情还款建议可见）→ 案件列表（5 条）| |
| 督导小李 | 13000000003 | 督导工作台 → 通话记录列表 → 话术标注（空列表正常）| |
| 内勤小张 | 13000000004 | 催收工作台 → 我的案件（5 条，已分配）| |
| 外勤小王 | 13000000005 | 催收工作台 → 我的案件（空列表，未分配）| |

## 已发现 bug（按 commit）

| Bug | 修复 commit | 备注 |
|-----|------------|------|
| （暂无）| — | Sprint 6 T2 冒烟全绿，无 bug 修复 |

## 已知遗留问题

无。如有新问题在此归档，并同步写入 `docs/KNOWN_ISSUES.md`。
