# Sprint 6 — MVP 验收冒烟 + Hardening 设计

> 类型：hardening sprint（不开发新功能）
> 范围：修今天冒烟发现的坑 + 第一次跑通 6 角色端到端 + 写部署手册
> 估时：0.5–1 天

## Context

5a + 5b 已合入 main（commit `560f947`）。今天的局部冒烟暴露 2 个集成 bug（alembic multiple heads、fastapi 0.115.4 + status_code=204 assert），均已修复并 push。但**完整的 6 角色端到端流程从未真实跑过**，docker 后端容器持续 crashed，`.env.example` 缺关键变量，**没有部署手册**。

Sprint 6 的目标是把这些"上线前最后一公里"的事做完，让 MVP 真正能被新人/客户在新机器上 30 分钟内跑起来。

## 不做什么

- ❌ 不开发新功能
- ❌ 不重构架构
- ❌ 不补 Playwright E2E 自动化测试（ROI 不够，先靠人工 E2E 把现有问题挖出来；如修完仍觉得脆再单独立 sprint）
- ❌ 不补 backend integration test（同上）

## 做什么（3 个任务）

### T1：修 docker 基座 + 补全 env 模板
- `poc/backend/.env.example` 加 `AUTOLUYIN_AES_KEY` 占位 + 安全注释
- `poc/docker-compose.yml` 后端服务 image 用本地 build 而非缓存；加 healthcheck；加 entrypoint 自动 run `alembic upgrade head`
- 验证：`docker compose up -d` 后所有容器 healthy，`curl /api/openapi.json` 200

### T2：seed 脚本 + 6 角色端到端冒烟
- `poc/backend/scripts/seed_demo.py`：种 1 租户 + 6 角色用户 + 5 案件 + 1 风控关键词 + 1 话术
- 浏览器手动跑：每个角色登录 → 点关键页面 → 记 console error
- `docs/E2E_SMOKE.md`：6 角色逐项检查清单（沉淀本次 + 后续每次冒烟用）
- 跑过程中发现的 bug：用 subagent 修，每个 bug 一个 commit

### T3：部署手册
- `docs/DEPLOYMENT.md` 章节：
  - 先决条件（docker / python / node 版本）
  - 本地 dev 启动（5 步，能跑通）
  - 环境变量清单（含安全级别说明）
  - Alembic 迁移流程（含 multiple heads 处理 / 回滚）
  - 故障排查（今天踩的坑都收录）
- README.md 顶部加一行链接到 DEPLOYMENT.md

## DoD（验收标准）

- [ ] `git clone` + 跟着 `DEPLOYMENT.md` 走，新人 30 分钟内跑起来
- [ ] `docker compose up -d` 后 `autoluyin-backend` 持续 healthy（不再 crash loop）
- [ ] 6 角色都能登录 + 各自主页加载无 console red error
- [ ] `E2E_SMOKE.md` 检查清单全 ✅（含本次发现的 bug 已修）
- [ ] 后端 188 测试无回归

## 风险与对策

| 风险 | 对策 |
|------|------|
| E2E 走过程中挖出大量 bug，超时 | 设上限：单 bug 修复 ≤ 30 分钟；超过的归档到 docs/KNOWN_ISSUES.md 留下次 sprint |
| docker 健康检查阻塞前端开发 | 不强求"完美 docker"——本地 uvicorn + docker postgres 是合法工作流，DEPLOYMENT.md 两种都写 |
| 部署手册无人验证 | 写完后我再用一个 fresh subagent 当"新人"按手册走一遍 |
