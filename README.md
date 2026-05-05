# 有证慧催 — 物业外呼录音 + 云端 ASR 系统

> 部署 / 本地启动看 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
> 端到端冒烟看 [docs/E2E_SMOKE.md](docs/E2E_SMOKE.md)

SaaS 多租户物业外呼录音系统，覆盖物业费催收和业委会投票邀请两个场景。

**技术栈：** FastAPI + PostgreSQL + Redis + Celery（后端）· Refine.dev + shadcn/ui（PC 前端）· Kotlin Android（端侧录音上传）

---

## 快速开始

```bash
git clone <repo> && cd autoluyin
cp poc/backend/.env.example poc/backend/.env
cd poc && docker compose up -d
docker exec autoluyin-backend python -m scripts.seed_demo
cd ../frontend && npm install && npm run dev
# 浏览器：http://localhost:5173
```

详细步骤、环境变量说明、故障排查见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

---

## 文档导航

| 文档 | 用途 |
|------|------|
| [docs/PRD.md](docs/PRD.md) | 产品需求，所有产品决策的最终落点 |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | 本地开发、staging/prod 部署、迁移、故障排查 |
| [docs/E2E_SMOKE.md](docs/E2E_SMOKE.md) | 端到端冒烟清单（6 角色账号 + 验收矩阵）|
| [docs/DESIGN_SPEC.md](docs/DESIGN_SPEC.md) | PC 端设计规范 |
| [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md) | 三端编码规范（Python / TypeScript / Kotlin）|
| [docs/TESTING_STANDARDS.md](docs/TESTING_STANDARDS.md) | 测试标准与覆盖率目标 |
| [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) | P0 页面 DoD 与验收标准 |

## 目录结构

```
autoluyin/
├── docs/          ← 所有文档
├── poc/
│   ├── backend/   ← FastAPI 后端（Python 3.12）
│   ├── android/   ← Kotlin Android 端
│   └── docker-compose.yml
└── frontend/      ← Refine.dev + shadcn/ui（TypeScript）
```
