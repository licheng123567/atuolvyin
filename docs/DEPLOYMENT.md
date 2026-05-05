# 部署手册

> 本手册覆盖本地开发、staging/prod 差异、Alembic 迁移、故障排查与回滚。
> 配合 [docs/E2E_SMOKE.md](E2E_SMOKE.md) 一起看（冒烟账号、API 测试矩阵在那边）。

---

## 1. 先决条件

| 工具 | 最低版本 | 说明 |
|------|---------|------|
| Docker Desktop | 24.0 | macOS / Linux；Windows 用 WSL2 |
| Python | 3.12 | 仅本地跑后端单元测试时需要，docker 内已包含 |
| Node.js | 20+ | 仅本地开发前端时需要 |

**端口占用检查（启动前确认这些端口空闲）：**

| 端口 | 服务 | 可通过 .env 覆盖 |
|------|-----|----------------|
| 18000 | backend API | `BACKEND_HOST_PORT` |
| 25432 | PostgreSQL | `POSTGRES_HOST_PORT` |
| 16379 | Redis | `REDIS_HOST_PORT` |
| 19000 | MinIO（仅 minio profile） | `MINIO_HOST_PORT` |
| 19001 | MinIO 控制台（仅 minio profile） | `MINIO_CONSOLE_HOST_PORT` |
| 5173 / 5174 | Vite dev server | Vite 自动递增 |

```bash
# 快速检查端口
lsof -i :18000 -i :25432 -i :16379 2>/dev/null
```

---

## 2. 本地开发（6 步起来）

```bash
# 步骤 1：clone
git clone <repo> && cd autoluyin

# 步骤 2：配 env（只需做一次）
cp poc/backend/.env.example poc/backend/.env
# 编辑 poc/backend/.env
# - dev 环境下所有默认值可直接用，无需改动
# - 如需真实 ASR/LLM，参见"环境变量清单"章节

# 步骤 3：启动 docker（含 postgres + redis + backend + celery_worker）
cd poc && docker compose up -d

# 步骤 4：等容器 healthy（backend 启动时自动运行 alembic upgrade head）
docker ps --filter name=autoluyin- --format '{{.Names}}: {{.Status}}'
# 期望输出（backend 可能需要 30-60s）：
#   autoluyin-backend: Up N seconds (healthy)
#   autoluyin-celery:  Up N seconds
#   autoluyin-pg:      Up N seconds (healthy)
#   autoluyin-redis:   Up N seconds (healthy)

# 步骤 5：写入 Demo 种子数据（幂等，可重复跑）
docker exec autoluyin-backend python -m scripts.seed_demo
# 首次：输出 [created] 若干行
# 再次：输出 [exists] 若干行（幂等，无副作用）

# 步骤 6：启动前端 dev server（另开终端）
cd ../frontend && npm install && npm run dev
# 浏览器：http://localhost:5173（或 5174 如 5173 占用）
# 登录账号见 docs/E2E_SMOKE.md（密码统一 Demo@123!）
```

**验证 API 可达：**
```bash
curl -sf http://localhost:18000/api/openapi.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('endpoints:', len(d['paths']))"
# 期望：endpoints: 45（或更多）
```

**启用 MinIO（可选，默认用 local 存储）：**
```bash
cd poc && docker compose --profile minio up -d
# MinIO 控制台：http://localhost:19001（minioadmin / minioadmin_dev）
```

---

## 3. 环境变量清单

> 文件路径：`poc/backend/.env`（从 `poc/backend/.env.example` 复制）

### 数据库 / 基础设施

| 变量 | 必须 | 说明 | 示例 / 默认 | prod 是否要换 |
|------|-----|------|------------|-------------|
| `DATABASE_URL` | 是 | PostgreSQL 连接串；docker 内服务名替换 localhost | `postgresql+psycopg://autoluyin:autoluyin_dev@localhost:25432/autoluyin` | 是（改密码）|
| `REDIS_URL` | 否 | Celery broker；docker compose 自动注入 | `redis://redis:6379/0` | 是（改密码）|

### 存储

| 变量 | 必须 | 说明 | 示例 / 默认 | prod 是否要换 |
|------|-----|------|------------|-------------|
| `STORAGE_BACKEND` | 是 | 三选一：`local` / `minio` / `oss` | `local` | 是（改为 `oss`）|
| `LOCAL_STORAGE_ROOT` | 条件 | `local` 模式录音写入路径（容器内） | `/tmp/autoluyin_recordings` | N/A |
| `LOCAL_STORAGE_PUBLIC_BASE` | 条件 | `local` 模式对外签名 URL 前缀；ASR 需要能访问此地址 | `http://localhost:18000` | 是（改域名）|
| `RECORDING_SIGN_SECRET` | 是 | 录音签名 HMAC key；`local` 模式防盗链 | `dev-secret-change-in-prod` | **必须换**（`openssl rand -hex 32`）|
| `OSS_ACCESS_KEY_ID` | 条件 | `oss` 模式阿里云 AK | — | — |
| `OSS_ACCESS_KEY_SECRET` | 条件 | `oss` 模式阿里云 SK | — | — |
| `OSS_ENDPOINT` | 条件 | `oss` 模式 endpoint（建议内网）| `oss-cn-hangzhou-internal.aliyuncs.com` | — |
| `OSS_BUCKET` | 条件 | `oss` 模式 bucket 名 | `autoluyin-recordings` | — |

### 安全

| 变量 | 必须 | 说明 | 示例 / 默认 | prod 是否要换 |
|------|-----|------|------------|-------------|
| `AUTOLUYIN_AES_KEY` | **是** | 手机号 AES-256 加密密钥；64 hex 字符 = 32 字节；缺失时 backend 启动即报错退出 | `0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef` | **必须换**（见下）|

生成新 key：
```bash
openssl rand -hex 32
```

### LLM / ASR

| 变量 | 必须 | 说明 | 示例 / 默认 | prod 是否要换 |
|------|-----|------|------------|-------------|
| `LLM_BACKEND` | 是 | `mock`（假结果）/ `api`（真 LLM）| `mock` | 是（`api`）|
| `LLM_API_KEY` | 条件 | `api` 模式 LLM key | `sk-placeholder` | **必须换** |
| `LLM_BASE_URL` | 条件 | `api` 模式 LLM endpoint | `https://api.deepseek.com` | 视供应商 |
| `LLM_MODEL` | 条件 | 模型名 | `deepseek-chat` | 视供应商 |
| `ASR_BACKEND` | 是 | `mock`（假文字稿）/ `dashscope`（阿里云）| `mock` | 是（`dashscope`）|
| `DASHSCOPE_API_KEY` | 条件 | DashScope ASR key；`dashscope` 模式必填 | — | **必须填** |

---

## 4. Alembic 迁移

backend 容器启动时会**自动执行** `alembic upgrade head`（见 `docker-compose.yml` command 字段），通常无需手动干预。

**手动操作（在容器内执行）：**

```bash
# 查看当前版本
docker exec autoluyin-backend alembic current
# 期望：1120fc740bba (head) (mergepoint)

# 升级到最新
docker exec autoluyin-backend alembic upgrade head

# 回滚一步
docker exec autoluyin-backend alembic downgrade -1

# 查看完整迁移历史
docker exec autoluyin-backend alembic history --verbose

# 查看所有 head（正常情况只有 1 个）
docker exec autoluyin-backend alembic heads
```

**多 head 处理（开发分支合并时常见）：**

Sprint 5a（风险关键词）和 Sprint 5b（话术库）均基于同一 `down_revision = 4001a1b2c3d4`，合并后产生两个并行 head：`5a001riskword` 和 `5b001`。处理方式：

```bash
# 1. 确认有两个 head
docker exec autoluyin-backend alembic heads
# 输出示例：
#   5a001riskword (head)
#   5b001 (head)

# 2. 创建 merge migration（本项目已存在：1120fc740bba）
docker exec autoluyin-backend alembic merge -m "merge sprint 5a+5b heads" 5a001riskword 5b001
# 这会在 alembic/versions/ 生成一个新 merge 文件

# 3. 升级
docker exec autoluyin-backend alembic upgrade head
```

> 历史背景：`poc/backend/alembic/versions/1120fc740bba_merge_sprint_5a_5b_heads.py` 就是这条 merge migration，已包含在仓库中，`down_revision = ('5a001riskword', '5b001')`，Sprint 6 后 `alembic current` 应显示 `1120fc740bba (head)`。

---

## 5. Staging / Prod 差异

**环境矩阵：**

| 变量 | dev | staging | prod |
|------|-----|---------|------|
| `AUTOLUYIN_AES_KEY` | 占位 64 hex | **必须重新生成** | **必须重新生成 + 严格保密** |
| `LLM_BACKEND` | `mock` | `api` | `api` |
| `LLM_API_KEY` | 占位 | 真实 key | 真实 key（KMS 管理）|
| `ASR_BACKEND` | `mock` | `dashscope` | `dashscope` |
| `DASHSCOPE_API_KEY` | 空 | 真实 key | 真实 key |
| `STORAGE_BACKEND` | `local` | `oss` | `oss` |
| `RECORDING_SIGN_SECRET` | `dev-secret-...` | **必须换** | **必须换** |
| `DATABASE_URL` 密码 | `autoluyin_dev` | 强密码 | 强密码 |

**Prod 额外步骤：**

```bash
# 1. 生成强密钥
openssl rand -hex 32   # 用于 AUTOLUYIN_AES_KEY
openssl rand -hex 32   # 用于 RECORDING_SIGN_SECRET

# 2. 关闭 FastAPI 文档（在 app/main.py 或通过环境变量）
# FastAPI 实例 docs_url=None, redoc_url=None（生产不暴露 /docs）

# 3. 使用 prod compose（Caddy 自动 HTTPS + 撤销内部端口公网暴露）
cd poc
vi caddy/Caddyfile   # 替换 your-domain.com 为备案域名，更改 admin@... 邮箱
vi .env              # 填入所有 prod 变量

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 4. 服务器安全组只放 22 / 80 / 443
```

**Caddy 配置**：`poc/caddy/Caddyfile` 已提供模板，包含：
- `api.your-domain.com` → 反代 `backend:8000`，自动 Let's Encrypt HTTPS，录音上传上限 200MB
- MinIO 数据口（`recording.your-domain.com`）默认注释，仅 `STORAGE_BACKEND=minio` 时启用
- MinIO 控制台 `:9001` 彻底不暴露，只能 SSH tunnel 访问：`ssh -L 9001:localhost:9001 user@server`

---

## 6. 故障排查

| 症状 | 排查命令 | 修复方法 |
|------|---------|---------|
| `autoluyin-backend` 一直 restarting | `docker logs autoluyin-backend --tail 50` | 看具体错误；最常见原因见下表 |
| `AUTOLUYIN_AES_KEY must be set` | `grep AUTOLUYIN_AES_KEY poc/backend/.env` | 确认 .env 中存在该变量且为 64 hex 字符；若无：`openssl rand -hex 32 >> poc/backend/.env`（手动格式化）|
| `alembic` 报 `Multiple head revisions` | `docker exec autoluyin-backend alembic heads` | 用 `alembic merge` 合并（见第 4 章） |
| `pyahocorasick` 编译失败（docker build 报错）| `docker compose build backend 2>&1 \| grep ahocorasick` | Dockerfile 需 `build-essential`；Sprint 6 已修，确认 Dockerfile 中有 `apt-get install -y build-essential` |
| FastAPI 启动报 `Status code 204 must not have a response body` | `docker logs autoluyin-backend \| grep "204"` | 在路由装饰器加 `response_class=Response, response_model=None`；Sprint 6 已全部修复 |
| `autoluyin-backend` unhealthy 但未 restart | `docker exec autoluyin-backend curl -sf http://localhost:8000/api/openapi.json` | healthcheck 用 `/api/openapi.json`；若 uvicorn 起来但路由有报错，看 `docker logs` 具体 traceback |
| 前端 dev server 白屏 / console 红错 | 浏览器开发者工具 → Network / Console | 确认 backend healthy；检查 CORS 配置（`ALLOWED_ORIGINS`）|
| 端口冲突（`address already in use`）| `lsof -i :18000` | 修改 `poc/backend/.env` 中对应 `*_HOST_PORT` 变量，重启 compose |
| `docker compose up` 后镜像旧（新代码未生效）| — | `docker compose build --no-cache backend && docker compose up -d backend` |
| Celery worker 无法连 Redis | `docker logs autoluyin-celery \| head -30` | 确认 `REDIS_URL` 正确；容器内 redis 服务名是 `redis`，不是 `localhost` |

---

## 7. 回滚流程

### 代码回滚

```bash
# 1. revert commit（生成一个新的反向提交，保留历史）
git revert <commit-sha>
git push origin main

# 2. 重建并重启 backend 容器
cd poc
docker compose build backend
docker compose up -d backend
# backend 重启时自动运行 alembic upgrade head（与新代码版本对应）
```

### DB 回滚

```bash
# 回滚到指定 revision（例：回到 4001a1b2c3d4）
docker exec autoluyin-backend alembic downgrade 4001a1b2c3d4

# 回滚一步
docker exec autoluyin-backend alembic downgrade -1
```

> **注意**：回滚前确认下游数据依赖。含 `DROP TABLE` / `DROP COLUMN` 的迁移回滚会导致数据丢失，prod 操作前务必备份。

### 完整重置（dev only，清空所有数据）

```bash
# ⚠️ 以下命令删除所有数据卷，仅在开发环境执行
cd poc
docker compose down -v            # 停容器 + 删数据卷（pg_data / recordings_data）
docker compose up -d              # 重新起（backend 自动 alembic upgrade head）
docker exec autoluyin-backend python -m scripts.seed_demo   # 重新写入 Demo 数据
```

---

## 附录：快速命令速查

```bash
# 查看所有容器状态
docker ps --filter name=autoluyin- --format '{{.Names}}: {{.Status}}'

# 实时跟踪 backend 日志
docker logs autoluyin-backend -f

# 进入 backend 容器 shell
docker exec -it autoluyin-backend bash

# 直连 PostgreSQL
docker exec -it autoluyin-pg psql -U autoluyin -d autoluyin

# 查看当前 alembic 版本
docker exec autoluyin-backend alembic current

# 运行端到端 API 冒烟（6 角色）
docker exec -e BACKEND_URL=http://localhost:8000 autoluyin-backend python -m scripts.api_smoke

# 查看 API 文档（dev 环境）
open http://localhost:18000/docs
```
