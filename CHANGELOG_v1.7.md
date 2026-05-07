# v1.7 — 主版本 major bump 全套

发布周期：2026-05-07（v1.6.5 → v1.7.4，共 6 个 tag，纯依赖升级 + 1 个安全 patch）

> v1.6 是 polish；v1.7 是**版本债清扫**。把"应升但有兼容风险"的 6 大主依赖在一个迭代内全部落地，每项独立 tag + GH release，可单独回滚。

## 总览

| Tag | 提交 | 主题 | 风险 | 测试 |
|---|---|---|---|---|
| v1.6.5 | `37c337d` | @types/node 25 + pyahocorasick 2 | 低/中 | 527+150 ✅ |
| v1.7.0 | `ee8a162` | passlib → bcrypt 5（架构变更） | 高 | 527+150 ✅ |
| v1.7.1 | `5212a8c` | celery 5.6 + redis 6.4（redis 7 受 kombu 锁） | 中 | 527+150 ✅ |
| v1.7.2 | `ea87476` | react 18→19 + Refine v5 API 收尾 | 高 | 527+150 ✅ |
| v1.7.3 | `305a2bc` | tailwind v3.4 → v4.2（compat 模式） | 高 | 527+150 ✅ |
| v1.7.4 | `df734dd` | pytest 9（CVE-2025-71176） | 中 | 527+150 ✅ |

测试基线在每一步都全绿。

## 详细变更

### v1.6.5 — type-only + 风控核心

- `@types/node` 24.12 → 25.6 — 跟 Node major bump，纯 type，无 runtime 影响
- `pyahocorasick` 1.4.4 → 2.3.1 — Aho-Corasick 自动机；2.x 是 typing + perf 升级，public API（`add_word` / `make_automaton` / `iter` / `len`）完全不变；`app/risk/keyword_matcher.py` 0 改动

### v1.7.0 — passlib 永别（架构层）

passlib 1.7.4 已 **archived**，不再维护，且与 bcrypt ≥ 5.x 不兼容（之前被迫 pin bcrypt==4.0.1）。本版本剥离 passlib，改用 bcrypt 官方库直接调用。

**变更**：
- `poc/backend/app/core/security.py`
  - 删除 `CryptContext` / `pwd_context`
  - `get_password_hash` → `bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()`（cost 12 默认）
  - `verify_password` → `bcrypt.checkpw(plain.encode(), hashed.encode())`；malformed hash 安全 fallback `False`（不泄漏内部细节）
- `requirements.txt`：删 `passlib==1.7.4`，bcrypt 4.0.1 → 5.0.0
- 测试 `test_auth.py`：删除本地 hardcoded `CryptContext`，改 `from app.core.security import get_password_hash`

**向后兼容**：DB 中现有 `password_hash` 是标准 bcrypt 60 字符串（`$2b$12$...`），bcrypt 4 / 5 跨版本 100% 互验证 — 无需用户迁移。

### v1.7.1 — celery + redis（受上游锁定）

期望 redis-py 5 → 7，但 kombu 5.6.2（celery 当前最新依赖的最新版）仍要求 `redis<6.5`，celery 5.6.3 通过 `kombu[redis]` extra 传递这条约束。

**可达上限**：
- celery 5.3.6 → 5.6.3（minor +3）
- redis 5.0.8 → 6.4.0（major +1，仍在 kombu 允许范围）

**业务影响**：本仓 redis 仅作为 celery broker URL（`app/worker/celery_app.py`），无 Python 客户端直调；smoke 验证 `celery_app` 可正常 import + 读 broker_url。

**待解锁**：等 kombu/celery 释放 redis ≥ 7 兼容后，本仓可一并升 redis 7。

### v1.7.2 — react 19 + 收尾 Refine v5 残余

**主升级**：
- react / react-dom 18.3.1 → 19.2.6
- @types/react / @types/react-dom 18.3.x → 19.2.x

react 19 自身 0 改动需要：tsc 干净；150 frontend 测试全绿。v1.6.4 已采用的 `useRef` init 模式在 react 19 StrictMode 重挂载下表现良好。

**附带修复 13 个 pre-existing build error**（`tsc -b` 触发，`tsc --noEmit` 漏掉）—  v1.1 Refine v4 → v5 迁移 PR (`c2680af`) 漏迁的 5 个文件：

| 文件 | 错误数 | 修复 |
|---|---|---|
| `NotificationBell.tsx` | 1 | `useCustom({ ..., refetch })` → `query.refetch` |
| `ops/law-firms/index.tsx` | 1 | 同上 |
| `ops/legal-workstation/index.tsx` | 9 | `xQuery.refetch()` → `xQuery.query.refetch()` |
| `super/blockchain-config/index.tsx` | 1 | `useCustom<T \| null>` → `useCustom<T>`（BaseRecord 约束） |
| `supervisor/risk-events/index.tsx` | 1 | `queryResult` 字段已删除，改 `query.refetch` |

`tsc -b` + `vite build` + 150 vitest 全绿。

### v1.7.3 — tailwind v4

tailwindcss 3.4.19 → 4.2.4。**compat 模式落地**（最小化代码改动）：

- `postcss.config.js`：插件入口 `tailwindcss: {}` → `'@tailwindcss/postcss': {}`（v4 拆出独立 PostCSS 包）
- `src/index.css`：`@tailwind base/components/utilities` → `@import "tailwindcss"` + `@config "../tailwind.config.ts"`
- 新依赖：`@tailwindcss/postcss@4.2.4`、`tailwind-merge@3.5.0`（与 v4 utility 体系对齐）

**不动**：
- `tailwind.config.ts`（colors / spacing / borderRadius / fontFamily extend 全部沿用，v4 通过 `@config` 指令照常生效）
- `design-system.css` 的 `:root` token 和 shadcn HSL 变量

**输出对比**：dist css 30 KB → 39 KB / gzip 6.4 KB → 8.0 KB（v4 默认 utility 集合略大，可按需配置 hover/focus prefix 精简，非紧急）。

**未来**：CSS-first config（迁 theme 到 `@theme {}` 块、删 tailwind.config.ts）作为独立 sprint 任务，本次仅完成框架升级。

### v1.7.4 — pytest CVE 安全 patch

pip-audit 在 v1.7.3 release 后扫描发现：`pytest 8.3.5` CVE-2025-71176（fix 9.0.3）。

**变更**：
- pytest 8.3.5 → 9.0.3
- pytest-asyncio 0.24.0 → 1.3.0（major bump，pytest 9 必需；API 稳定）
- pytest-cov 6.0.0 → 7.1.0（major bump，CLI 兼容）

527 测试全绿；`asyncio_mode=auto` / `cov` 配置无需调整。

## 漏洞处置全景

| 包 | CVE | v1.6.0 状态 | v1.7.4 状态 |
|---|---|---|---|
| starlette 0.41.3 | CVE-2025-54121 | open | ✅ v1.6.1（fastapi 0.136 → starlette 0.49.1） |
| starlette 0.41.3 | CVE-2025-62727 | open | ✅ v1.6.1 |
| pytest 8.3.5 | CVE-2025-71176 | n/a（升级后才暴露） | ✅ v1.7.4（pytest 9.0.3） |
| pip 26.0 | CVE-2026-3219 | open | 🟡 上游无 fix；监控 |
| pip 26.0 | CVE-2026-6357 | open | 🟡 dev tool；本地 `pip install -U pip` 即可 |

至 v1.7.4：**npm 0 vuln · pip 仅 2 项 dev-tool CVE**（无 runtime 风险）。

## 未升级（产品/上游决策）

| 包 | 现 | 最新 | 阻塞原因 |
|---|---|---|---|
| starlette | 0.49.1 | 1.0.0 | 等 FastAPI 0.137+ 释放兼容 |
| redis | 6.4.0 | 7.4.0 | 等 kombu 释放 `redis>=7` |
| pydantic | 2.9.2 | 2.13.4 | 4 个 minor 跳跃，需独立 sprint 评估 |
| pydantic-settings | 2.6.1 | 2.14.0 | 同上 |
| alembic | 1.14.1 | 1.18.4 | 4 个 minor 跳跃 |
| cryptography | 47 | 48 | major bump，影响范围核查 |

## 迁移命令

```bash
# 后端（系统 python 装包；CI 走 requirements.txt）
cd poc/backend
pip install -U -r requirements.txt

# 前端
cd frontend
npm install
npm run build       # 验证 tsc -b + vite build
npm test            # 150 vitest
```

## 回滚策略

每个 v1.7.x tag 独立可回滚：

```bash
# 回滚单个 tag（例如 react 19 出问题）
git revert ea87476     # v1.7.2 commit
# 或重置到上一 tag
git reset --hard v1.7.1
```

passlib → bcrypt 5（v1.7.0）是单向不可回滚的代码替换；如需恢复 passlib 需手动 revert + reinstall + 验证 bcrypt 4 兼容。
