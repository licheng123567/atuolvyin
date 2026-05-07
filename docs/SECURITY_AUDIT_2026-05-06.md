# 安全 + 依赖审计 — 2026-05-06（v1.6.0 后）

工具：`npm audit` + `pip-audit`（PyPA 官方）+ `npm outdated` + `pip list --outdated`

## 总览

| 维度 | 前端 | 后端 |
|---|---|---|
| 漏洞数 | **0** ✅ | 4 项（已处置 2/4） |
| 待升级依赖 | 10 项（多为 major bump） | 19 项 |

## 后端漏洞与处置

| 包 | 当前 | CVE | 修复版本 | 严重度 | 处置 |
|---|---|---|---|---|---|
| `starlette` | 0.41.3 | CVE-2025-54121 | 0.47.2 | 中 | ✅ **已修**（fastapi 0.136.1 → starlette 0.49.1） |
| `starlette` | 0.41.3 | CVE-2025-62727 | 0.49.1 | 中 | ✅ **已修**（同上） |
| `pip` | 26.0 | CVE-2026-3219 | — 无 fix | 低 | 🟡 dev 工具，非 runtime；监控 fix 发布 |
| `pip` | 26.0 | CVE-2026-6357 | 26.1 | 低 | 🟡 dev 工具，本地开发各自升级 |

### 升级路径细节

`fastapi==0.115.4` 通过传递依赖锁住 `starlette<0.42`。要升 starlette ≥ 0.49.1 必须连带升 FastAPI：

| FastAPI | starlette 区间 |
|---|---|
| 0.115.4 (旧) | `>=0.40.0,<0.42.0` |
| 0.118.0 | `>=0.40.0,<0.49.0`（仍不够） |
| 0.136.1 (新) | `>=0.46.0`（无上限）|

并附带要求：
- `pydantic>=2.9.0`（已 2.9.2 ✓）
- `python-multipart>=0.0.18`（从 0.0.17 → 0.0.18，无 BC break）

527 后端测试全绿（含 alembic round-trip）。仅出现 4 条 deprecation warning：
- starlette 0.49 把 `HTTP_422_UNPROCESSABLE_ENTITY` rename 为 `HTTP_422_UNPROCESSABLE_CONTENT`（旧名仍可用，下次 major 才删）

## 待升级依赖（v1.7+ 评估）

### 前端（major bump，**未升**）

| 包 | 现 | 最新 | 评估 |
|---|---|---|---|
| react / react-dom | 18.3.1 | 19.2.6 | React 19：Strict Effects、新 hook、Server Components — 工作量大；当前稳定，不主动升 |
| @types/react(-dom) | 18.3 | 19.x | 跟随 react |
| tailwindcss | 3.4.19 | 4.2.4 | tailwind v4 重大配置变更（@theme + CSS-first），design-system.css 全部重写 — 需要专项 sprint |
| vitest | 3.2.4 | 4.1.5 | API 微调，主要是性能与 ESM 改进；可在 v1.7 内顺手升 |
| lucide-react | 0.511.0 | 1.14.0 | 1.0 是稳定标志位，几乎无 BC break；**v1.7 可升** |
| tailwind-merge | 2.6.1 | 3.5.0 | 跟随 tailwind v4 升 |
| vite | 8.0.10 | 8.0.11 | patch — `npm i` 即生效 |
| @types/node | 24.12 | 25.6 | 跟随 Node major |

### 后端（多数 patch / minor，**未升**）

| 包 | 现 | 最新 | 评估 |
|---|---|---|---|
| celery | 5.3.6 | 5.6.3 | 都是 5.x，可升；当前未在关键路径活跃使用 |
| cryptography | 47 | 48 | 跟随 OpenSSL；建议跟 starlette 一起在下次 sprint 升 |
| fastapi | 已升 0.136.1 | — | ✅ |
| starlette | 已升 0.49.1 | — | ✅ |
| pydantic / pydantic-core | 2.13.3 / 2.46.3 | 2.13.4 / 2.46.4 | patch — 顺手升 |
| psycopg / psycopg-binary | 3.3.3 | 3.3.4 | patch |
| redis | 5.0.4 | 7.4.0 | major bump，redis-py 7 改动大；redis 客户端在 ws/notification 重度使用，需要专项 sprint |
| uvicorn | 0.32.0 | 0.46.0 | 14 个 minor；伴随 FastAPI 升级一起评估 |
| dashscope | 1.20.11 | 1.25.17 | 阿里 ASR SDK；监控 deprecate 字段 |
| pyahocorasick | 1.4.4 | 2.3.1 | 风控关键词匹配核心；2.x 主要是 typing + perf，**v1.7 可升** |
| bcrypt | 4.0.1 | — | 不可升（passlib 1.7.4 不兼容 bcrypt 5.x；passlib 已 archived，长期看要换 argon2-cffi 或 bcrypt 直用） |

## v1.7 候选清单（基于本审计）

> 截至 2026-05-07 处理进度：v1.6.2/.3/.5 已批量落地 patch + 中风险 minor 升级；v1.7.0 已替换 passlib。

1. ~~lucide-react 0.511 → 1.14~~ — ✅ v1.6.3
2. ~~vitest 3 → 4~~ — ✅ v1.6.3
3. ~~patch-level 升级一批~~ — ✅ v1.6.2/.3
4. **redis-py 5 → 7**（高风险，专项）— pending
5. ~~bcrypt 5 + passlib 替换~~ — ✅ v1.7.0（passlib archived，重写为 bcrypt 直接调用）
6. **tailwind v4**（专项 sprint，影响 design-system.css 整套 token）— pending
7. **react 19**（专项 sprint，concurrent / strict effects 全面 review）— pending
8. ~~@types/node 24→25~~ — ✅ v1.6.5
9. ~~pyahocorasick 1.4→2.3~~ — ✅ v1.6.5

## 复测命令

```bash
# 前端
cd frontend && npm audit

# 后端
cd poc/backend && /path/to/python3.12 -m pip_audit
```

## 时间戳

- 审计时间：2026-05-06 23:10
- 审计执行人：autonomous loop（v1.6.0 release 后第 N 个 commit）
- 审计基线 commit：`b9971db`（plan 归档）
- 升级落地 commit：本文档同步入库
