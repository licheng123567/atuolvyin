# 编码规范

> 适用范围：PC 前端（TypeScript + React + Refine.dev）/ 后端（Python + FastAPI）/ Android（Kotlin）
> 与 DESIGN_SPEC.md §5-6 配套使用，不重复设计规范内容。

---

## 1. 后端（Python / FastAPI）

### 1.1 工具链

| 工具 | 用途 | 配置文件 |
|------|------|---------|
| ruff | Lint + import sort | `poc/backend/pyproject.toml` |
| mypy | 类型检查（strict 模式）| `poc/backend/pyproject.toml` |
| black | 格式化（ruff format 替代）| 同上 |

运行：
```bash
cd poc/backend
ruff check .          # lint
ruff format --check . # 格式检查
mypy app/             # 类型检查
```

### 1.2 命名约定

| 对象 | 约定 | 示例 |
|------|------|------|
| 模块/包 | snake_case | `case_service.py` |
| 类 | PascalCase | `CollectionCase` |
| 函数/变量 | snake_case | `get_case_by_id` |
| 常量 | SCREAMING_SNAKE | `MAX_RETRY_COUNT = 3` |
| Pydantic schema | `{Resource}{Action}` | `CaseCreateRequest`, `CaseResponse` |
| SQLAlchemy model | `{Entity}` | `CollectionCase`（等于实体名）|

### 1.3 必须遵守

- 所有函数必须有类型提示（参数 + 返回值），`-> None` 也要写
- 禁止裸 `dict` 作为函数返回值或参数；用 Pydantic model 或 TypedDict
- 禁止 `except Exception: pass`；最少 log 错误
- 手机号字段存储前必须加密，输出必须脱敏（`138****1234`）
- 多租户查询必须带 `tenant_id` 条件，禁止全表扫描
- 拨号接口调用前检查 `tenant_minute_usage`，超额返回 `403`

### 1.4 Router / Service 分层

```
routers/{module}.py     ← 仅做 HTTP 层：入参验证、权限校验、调用 service
services/{module}.py    ← 业务逻辑，不依赖 Request/Response 对象
models/{module}.py      ← SQLAlchemy ORM 定义
schemas/{module}.py     ← Pydantic 入参/出参
```

router 函数体最多 10 行；超过的逻辑移入 service。

### 1.5 错误响应格式

```python
# 正确
raise HTTPException(
    status_code=400,
    detail={"code": "ERR_CASE_NOT_FOUND", "message": "案件不存在"}
)
# 禁止
raise HTTPException(400, "案件不存在")  # 裸字符串
```

---

## 2. PC 前端（TypeScript / React / Refine.dev）

### 2.1 工具链

| 工具 | 用途 | 配置文件 |
|------|------|---------|
| ESLint | Lint | `frontend/.eslintrc.json` |
| Prettier | 格式化 | `frontend/prettier.config.js` |
| TypeScript strict | 类型检查 | `frontend/tsconfig.json` |

```bash
cd frontend
npm run lint      # ESLint
npm run format    # Prettier
npm run typecheck # tsc --noEmit
```

### 2.2 命名约定

| 对象 | 约定 | 示例 |
|------|------|------|
| React 组件 | PascalCase | `CaseListPage.tsx` |
| Hook | camelCase + `use` 前缀 | `useCaseFilters.ts` |
| 工具函数 | camelCase | `formatPhone.ts` |
| 类型/接口 | PascalCase | `CaseResponse` |
| 常量 | SCREAMING_SNAKE | `MAX_PAGE_SIZE` |

### 2.3 必须遵守

- 禁止 `any` 类型（等同编译错误，`tsconfig` 已设 `noImplicitAny: true`）
- 组件优先使用 shadcn/ui；自定义组件放 `src/components/`
- 数据请求统一用 Refine hooks：`useList` / `useShow` / `useCreate` / `useUpdate` / `useDelete`
- 图标只用 `lucide-react`，禁止混用其他图标库
- 禁止在组件内直接 `fetch()`；所有请求走 Refine dataProvider

### 2.4 文件结构

```
frontend/src/
├── pages/           ← 每个角色一个子目录 (admin/, supervisor/, agent/, ...)
│   └── admin/
│       ├── CasesPage.tsx
│       └── CaseDetailPage.tsx
├── components/      ← 跨页复用组件
├── hooks/           ← 自定义 hooks
├── providers/       ← authProvider, dataProvider, accessControlProvider
├── types/           ← 所有 TypeScript 类型（从 OpenAPI schema 生成）
└── lib/             ← 工具函数
```

---

## 3. Android（Kotlin）

### 3.1 工具链

ktlint（格式）+ detekt（静态分析），配置在 `poc/android/build.gradle.kts`。

### 3.2 必须遵守

- 网络请求通过 Coroutines + Retrofit2；禁止在主线程阻塞
- 手机号字段禁止明文 log：`Log.d("tag", phone)` 这样的代码必须在 CI 中被 detekt 拦截
- 包结构按功能划分：`feature.call` / `feature.task` / `core.network` / `core.storage`
- ViewModel 处理 UI 状态，Repository 处理数据，禁止在 Activity 直接调 Retrofit

---

## 4. 跨端规范

### 4.1 Commit 格式（Conventional Commits）

```
feat(case): add bulk assignment API
fix(call): prevent duplicate upload on retry
chore(ci): add ruff to PR lint check
test(models): add tenant isolation test
docs(prd): add minute pooling section
```

### 4.2 分支命名

```
feature/{ticket-or-description}   # 新功能
fix/{description}                 # bug 修复
chore/{description}               # 工程/配置变更
```

### 4.3 PR 合并前必须通过

1. `ruff check` + `ruff format --check`（后端）
2. `mypy app/`（后端）
3. `pytest` 全量通过，覆盖率 ≥ 80%（P0 模块）
4. `npm run lint` + `npm run typecheck`（前端）
5. 无 `# TODO:` 残留在关键路径（router / service / model）
