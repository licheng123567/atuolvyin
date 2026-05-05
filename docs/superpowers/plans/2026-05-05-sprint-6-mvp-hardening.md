# Sprint 6 — MVP 验收冒烟 + Hardening 实施计划

> **For agentic workers:** 由主对话直接驱动 subagent 执行，无双 reviewer 流程（hardening 改动小、可立验证）。

**Goal:** 修今天冒烟发现的坑 + 跑通 6 角色端到端 + 部署手册三件事，让 MVP 能被新人 30 分钟内跑起来。

**Architecture:** 不引入新架构。改动范围：docker / .env 模板 / seed 脚本 / 文档 / 在 E2E 中发现的 bug 修复。

**Tech Stack:** docker-compose + .env / Python seed / Markdown 文档

---

## Task 1：修 docker 基座 + 补全 env 模板

**Files:**
- Modify: `poc/backend/.env.example`
- Modify: `poc/docker-compose.yml`
- Modify: `poc/backend/Dockerfile`（如需）

**Steps:**

- [ ] **1.1** `.env.example` 在合适位置（手机号加密相关附近）追加：
  ```
  # AES-256 手机号加密密钥（64 hex 字符 = 32 字节）
  # dev 用占位即可；staging/prod 必须重新生成（openssl rand -hex 32）
  AUTOLUYIN_AES_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
  ```

- [ ] **1.2** `poc/docker-compose.yml` backend service：
  - 改 `image: poc-backend` → `build: ./backend`（强制本地 build 而非缓存）
  - 加 healthcheck：`test: ["CMD", "curl", "-f", "http://localhost:8000/api/openapi.json"]`，interval 10s
  - 加 `command:` 或 entrypoint：启动前先 `alembic upgrade head`，再 `uvicorn app.main:app`
  - 加 `env_file: ./backend/.env`（确保读取本地 env）

- [ ] **1.3** 验证：
  ```bash
  cd poc && docker compose down && docker compose build backend && docker compose up -d
  docker ps --filter name=autoluyin- --format '{{.Names}}: {{.Status}}'
  curl -sf http://localhost:18000/api/openapi.json | head -1   # 应该 200
  docker exec autoluyin-pg psql -U autoluyin -d autoluyin -c "SELECT version_num FROM alembic_version;"  # 1120fc740bba
  ```

- [ ] **1.4** Commit：`fix(infra): hotfix docker backend + env template`

---

## Task 2：seed 脚本 + 6 角色端到端冒烟

**Files:**
- Create: `poc/backend/scripts/seed_demo.py`
- Create: `docs/E2E_SMOKE.md`
- Bug 修复：随发现随改

**Steps:**

- [ ] **2.1** seed 脚本（运行：`python -m scripts.seed_demo`）建：
  - 1 个租户 `Demo 物业`
  - 6 角色用户（密码统一 `Demo@123!`）：
    - `platform_super` / phone `13000000000`
    - `platform_ops` / `13000000001`
    - `admin` / `13000000002`
    - `supervisor` / `13000000003`
    - `agent_internal` / `13000000004`
    - `agent_external` / `13000000005`
  - 5 个 OwnerProfile + 5 个 CollectionCase（不同欠费金额、不同月数）
  - 1 条风控关键词（"投诉"，level=L1）
  - 1 条话术（trigger_intent="经济困难"）
  - 幂等：重复跑不报错（用 `INSERT ... ON CONFLICT` 或先检查存在）

- [ ] **2.2** 跑 seed：`docker exec autoluyin-backend python -m scripts.seed_demo`，确认 6 用户、5 案件、1 关键词、1 话术写入。

- [ ] **2.3** 浏览器手动 E2E：
  ```
  https://localhost:5174 （或 docker 起在 5173）
  ```
  对每个角色：
  - 登录（用户名 = 手机号、密码 `Demo@123!`）
  - 进默认主页，看是否加载（无白屏 / 无 console red error）
  - 点至少 3 个核心页面（角色相关）
  - 记录所有问题到 `docs/E2E_SMOKE.md`

  6 角色至少跑：
  | 角色 | 必跑页面 |
  |------|---------|
  | platform_super | 系统健康、租户列表、成本看板 |
  | platform_ops | 运营大盘、租户列表、租户详情 |
  | admin | 仪表盘、案件列表、催收员管理、话术库 |
  | supervisor | 督导工作台、督导话术标注、升级案件 |
  | agent_internal | 案件列表、案件详情、（如能）实时通话页 |
  | agent_external | 案件列表（脱敏）、案件详情 |

- [ ] **2.4** 发现的每个 bug：
  - 写到 `docs/E2E_SMOKE.md` 的"已发现 bug"表
  - 立刻修（≤30 分钟搞定的修；超时归档到 `docs/KNOWN_ISSUES.md`）
  - 每个 fix 一个 commit：`fix(e2e): <短描述>`

- [ ] **2.5** `docs/E2E_SMOKE.md` 终态包含：
  - 6 角色检查清单（每条带 ☐ / ✅）
  - 已修 bug 列表（commit sha 链接）
  - 已知遗留问题（如有，带优先级）

- [ ] **2.6** Commit：`feat(infra): seed_demo + E2E_SMOKE checklist`（不含 bug fix，那些是单独 commit）

---

## Task 3：部署手册

**Files:**
- Create: `docs/DEPLOYMENT.md`
- Modify: `README.md`（顶部加链接）

**Steps:**

- [ ] **3.1** `docs/DEPLOYMENT.md` 结构：

  ```markdown
  # 部署手册

  ## 1. 先决条件
  - Docker Desktop ≥ 24.0
  - Python 3.12 + Node.js 20+（仅前端开发需要）
  - 端口空闲：18000（backend）、25432（postgres）、5173（frontend dev）

  ## 2. 本地开发（5 步起来）
  1. clone 仓库
  2. cp poc/backend/.env.example poc/backend/.env
  3. cd poc && docker compose up -d
  4. cd ../frontend && npm install && npm run dev
  5. 浏览器打开 localhost:5173

  ## 3. 环境变量清单
  | 变量 | 必须 | 说明 | 示例 |
  | ... |

  ## 4. Alembic 迁移
  - 升级到最新：`docker exec autoluyin-backend alembic upgrade head`
  - 看当前版本：`alembic current`
  - 多 head 处理：`alembic merge -m "..." <h1> <h2>`
  - 回滚一步：`alembic downgrade -1`

  ## 5. Staging / Prod 差异
  - AUTOLUYIN_AES_KEY 必须重新生成
  - LLM_BACKEND=api，配真实 LLM_API_KEY
  - ASR_BACKEND=dashscope，配 DASHSCOPE_API_KEY
  - STORAGE_BACKEND=oss，配 OSS_*

  ## 6. 故障排查
  - **autoluyin-backend 启动失败**：看 `docker logs`；常见 fastapi 0.115.4 + status_code=204 路由要 `response_class=Response, response_model=None`
  - **alembic 报 multiple heads**：用 `alembic merge` 命令
  - **`AUTOLUYIN_AES_KEY must be set`**：检查 `.env` 中是否有；64 hex 字符
  - ...（在 E2E 过程中发现的坑都收录）

  ## 7. 回滚流程
  - main 上 `git revert <commit>` + push
  - DB：`alembic downgrade <revision>`
  - 容器：`docker compose down && docker compose up -d`
  ```

- [ ] **3.2** README.md 顶部加：
  ```markdown
  > 部署 / 本地启动看 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
  ```

- [ ] **3.3** 用一个 fresh subagent 模拟新人按手册走一遍，记录卡点，回过头补强手册。

- [ ] **3.4** Commit：`docs: deployment manual + README link`

---

## Verification（Sprint 6 整体）

- [ ] `docker compose up -d` 所有容器 healthy（无 crashloop）
- [ ] `curl http://localhost:18000/api/openapi.json` 返回 200 + 45 endpoints
- [ ] 跑 seed → 6 角色登录 → 主页无 red error → E2E_SMOKE.md 全 ✅
- [ ] 后端测试 188 passed 无回归
- [ ] 部署手册被 fresh subagent 验证可走通

## 收尾

- [ ] 跑 `finishing-a-development-branch` skill：选项 1+2 同时（push + PR + 合 main）
- [ ] 通知用户 Checkpoint 1：批 1 完成，可开批 2
