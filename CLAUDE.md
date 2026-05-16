# 有证慧催 — 项目工作规范

## 项目概述

物业外呼录音 + 云端 ASR 系统。两个催收场景：物业费催收、业委会投票邀请。
SaaS 多租户，6 个组织角色 + 2 个平台角色（四维正交模型，见多租户关键规则），PC（Refine.dev + shadcn/ui）+ Android（Kotlin）+ 后端（FastAPI + PostgreSQL）。

## 权威文档（读代码前先读这里）

| 文档 | 用途 |
|------|------|
| `docs/PRD.md` | 权威需求，所有产品决策的最终落点 |
| `docs/DESIGN_SPEC.md` | PC 端设计规范，含组件约束、性能基线、交付 checklist |
| `docs/UI_GAPS.md` | PRD-UI 缺口追踪表，当前状态 |

## 技术栈

| 层 | 选型 |
|----|------|
| PC 前端 | TypeScript + React + **Refine.dev** + **shadcn/ui** + Tailwind CSS |
| 图标 | lucide-react（shadcn/ui 同源，禁止混用其他图标库）|
| 后端 | Python + FastAPI + SQLAlchemy 2.0 + PostgreSQL + MinIO |
| Android | Kotlin + Coroutines + Retrofit2 + OkHttp3 |
| 流程自动化 | n8n |
| 测试 — 后端 | pytest + httpx + testcontainers-postgres |
| 测试 — PC | Vitest + React Testing Library + Playwright |
| 测试 — Android | JUnit5 + MockK + Espresso |

## 目录结构

```
autoluyin/
├── docs/          ← PRD、设计规范、缺口报告、标准文档
├── ui/            ← HTML 原型（设计参考，不是生产代码）
│   └── assets/design-system.css  ← 设计 token 唯一来源
├── poc/
│   ├── backend/   ← FastAPI PoC（MVP 后端基础）
│   └── android/   ← Kotlin Android PoC
└── CLAUDE.md      ← 本文件
```

## 开发阶段（当前进度）

```
✅ A  PRD-UI 缺口排查（UI_GAPS.md 已生成）
✅ B  关键 P0 缺口补 UI（池化配额视图、项目负责人角色等）
✅ C  三份标准文档（CODING_STANDARDS / TESTING_STANDARDS / ACCEPTANCE）
✅ D  工程脚手架（eslint/ruff/CI/Alembic/Refine.dev 项目初始化）
⬜ E  MVP 全栈编码
```

**当前处于 D→E 过渡期，可以开始 MVP 编码。**

### Stage D 交付物清单
- `docs/CODING_STANDARDS.md` — 三端语言规范（Python/TS/Kotlin）
- `docs/TESTING_STANDARDS.md` — 测试框架、覆盖率目标、CI 配置
- `docs/ACCEPTANCE.md` — P0 页面 DoD 与端到端流程验收标准
- `poc/backend/pyproject.toml` — ruff + mypy + pytest 配置
- `poc/backend/app/models/` — SQLAlchemy 2.0 ORM 模型（18 个实体）
- `poc/backend/app/schemas/` — Pydantic v2 schema（含 PaginatedResponse 泛型）
- `poc/backend/tests/conftest.py` — testcontainers-postgres session fixture
- `poc/backend/alembic/` — 迁移脚本骨架（env.py 已接 Base.metadata）
- `frontend/` — Refine.dev v5 + Tailwind + shadcn/ui 初始化（tailwind.config.ts / components.json / postcss.config.js）
- `frontend/src/lib/utils.ts` — cn() 工具函数
- `frontend/src/types/index.ts` — 共享类型定义（UserRole / ApiError / PaginatedResponse）
- `.github/workflows/ci.yml` — 4 个 job（backend-lint / backend-test / frontend-lint / frontend-build）

## Skill 使用规则

### 自动触发（无需手动调用）

| 触发场景 | 生效 Skill |
|---------|-----------|
| 实现任何新功能或修 bug | `test-driven-development` — 先写测试再写代码，无例外 |
| 规划一个新功能或 Sprint | `brainstorming` → `writing-plans` — 先设计再动手 |
| 按计划执行任务 | `executing-plans` — 逐步推进，完成即更新 |
| 提交 PR / 合并代码前 | `finishing-a-development-branch` — lint + 测试 + 检查 TODO |
| 遇到 bug 需要排查 | `systematic-debugging` — 假设→验证→修复→补测试 |
| 前后端需要并行推进 | `using-git-worktrees` + `dispatching-parallel-agents` |
| 把产品决策写入 PRD | `prd-section-writer` — 读现有结构再起草，确认后写入 |
| 生成 API 骨架 | `api-contract-gen` — 从 PRD §21 推导 endpoint，生成 stub |

### 项目自定义 Skill 说明

- **`prd-section-writer`**：口头产品决策 → 结构化 PRD 章节。触发词：「写进PRD」「落到文档」「document this decision」
- **`api-contract-gen`**：PRD 页面操作 → FastAPI router stub + Pydantic schema。触发词：「生成接口」「写Schema」Stage D 启动时

## 编码约束（Stage D 正式文档前的临时规则）

### 通用
- 所有字符串字面量禁止硬编码 tenant_id / user_id
- API 路径统一前缀 `/api/v1/`
- 错误响应格式：`{"code": "ERR_XXX", "message": "..."}`

### 后端（Python）
- 类型提示强制，不允许裸 `dict` 作为函数返回值
- 新增路由必须有 Pydantic schema（不允许裸 dict 入参）
- 手机号存储 AES-256 加密，输出必须脱敏（`138****1234`）
- 拨号接口调用前必须检查 `tenant_minute_usage`，超额返回 `403 Quota Exceeded`
- 复用 `poc/backend/app/services/asr.py` 的 dispatcher 模式接入外部服务

### PC 前端（TypeScript）
- 严禁 `any` 类型（等同于编译错误）
- 组件优先使用 shadcn/ui，禁止重复造轮子
- 数据请求统一用 Refine `useList / useCreate / useUpdate / useDelete`
- 图标只用 `lucide-react`，禁止混用

### Android（Kotlin）
- 所有网络请求通过 Coroutines + Retrofit2，禁止在主线程阻塞
- 手机号字段禁止明文 log 输出

## 多租户关键规则

- 所有数据库查询必须带 `tenant_id` 条件（不允许全表扫描）
- 服务商（provider）的数据通过 `scope = provider:{id}` 隔离
- 跨租户操作只有平台超管角色可执行

### 角色模型（v2.2 四维正交，`feature/role-model-refactor` 已落地）

**四个维度：**
- `UserAccount.platform_role` ∈ {`superadmin`, `ops`} 或 `NULL` — 平台身份（平台用户无 membership）
- `UserTenantMembership.role` ∈ {`admin`, `project_manager`, `supervisor`, `agent`, `legal`, `coordinator`} — 6 个组织职能角色
- `UserTenantMembership.provider_id` — `NULL` = 物业侧；非 `NULL` = 服务商侧（**组织归属唯一依据**，旧 `source_type` 列已删除）
- `UserTenantMembership.work_mode` ∈ {`internal`, `external`} — 仅 `agent` 角色非 `NULL`，其余为 `NULL`

**端点鉴权守卫（`app/core/security.py`）：**
- `require_tenant_roles(*roles)` — 物业专用端点（断言 `provider_id IS NULL`）
- `require_provider_roles(*roles)` — 服务商专用端点（断言 `provider_id IS NOT NULL`）
- `require_roles(*roles)` — 跨两侧端点（凡角色元组含 `agent` 必须用此，不得用前两者）

**后端角色常量单一事实源：`app/core/roles.py`** — 禁止在其他文件散落角色字面量。

> 旧 11 角色枚举（`agent_internal`、`agent_external`、`provider_admin`、`project_manager_property`、`project_manager_provider`、`platform_super`、`platform_superadmin`、`platform_ops` 等）已全部废弃，禁止在新代码中使用。映射详见 `docs/superpowers/specs/2026-05-16-role-model-refactor-design.md` §5.1。

## 测试要求（零妥协）

- P0 模块行覆盖率 ≥ 80%
- 拨打/上传/ASR/计费关键路径 ≥ 90%
- 每个 bug 修复必须有对应的回归测试
- DB 集成测试用 testcontainers，禁止 mock 数据库

## Git 工作流

- 分支命名：`feature/xxx`、`fix/xxx`、`chore/xxx`
- Commit 格式：Conventional Commits（`feat:` `fix:` `chore:` `test:` `docs:`）
- PR 合并前必须通过：lint + unit tests + 无 `TODO:` 遗留在关键路径
- worktree 路径：`../autoluyin-{feature}` （`using-git-worktrees` skill 管理）
