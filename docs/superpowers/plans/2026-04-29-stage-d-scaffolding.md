# Stage D — 工程脚手架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 MVP 业务编码开始前，补全五层工程基础：标准文档 → ORM 模型 → API Schema → 工程脚手架 → CI，确保每个人拿到代码库后能立即运行、测试、开发。

**Architecture:** 后端扩展现有 PoC（`poc/backend/`），新增 SQLAlchemy ORM 模型层 + Alembic 迁移 + Pydantic Schema 层；前端在 `frontend/` 新建 Vite+React+Refine.dev 项目；根目录补充 CI 和统一 docker-compose。PoC 的四个 router 暂时保留裸 SQL，不在本阶段重写——重写在 Stage E。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic / Pydantic v2 / pytest / TypeScript 5 / React 18 / Refine.dev 4 / shadcn/ui / Vite / Tailwind CSS / GitHub Actions

---

## 文件清单

### 新建
```
docs/CODING_STANDARDS.md
docs/TESTING_STANDARDS.md
docs/ACCEPTANCE.md

poc/backend/pyproject.toml                    ← ruff + mypy + pytest 配置
poc/backend/.env.example
poc/backend/app/models/base.py
poc/backend/app/models/tenant.py
poc/backend/app/models/user.py
poc/backend/app/models/case.py
poc/backend/app/models/call.py
poc/backend/app/models/work.py
poc/backend/app/models/settlement.py
poc/backend/app/models/__init__.py
poc/backend/alembic.ini
poc/backend/alembic/env.py
poc/backend/alembic/versions/0001_initial.py
poc/backend/app/schemas/__init__.py
poc/backend/app/schemas/common.py
poc/backend/app/schemas/case.py
poc/backend/app/schemas/call.py
poc/backend/app/schemas/user.py
poc/backend/tests/__init__.py
poc/backend/tests/conftest.py
poc/backend/tests/test_models.py
poc/backend/tests/test_schemas.py

frontend/package.json
frontend/tsconfig.json
frontend/vite.config.ts
frontend/.eslintrc.json
frontend/prettier.config.js
frontend/src/main.tsx
frontend/src/App.tsx
frontend/src/providers/index.tsx
frontend/components.json                      ← shadcn/ui 配置

.github/workflows/ci.yml
```

### 修改
```
poc/backend/app/models/__init__.py            ← 空 → 导出所有模型
poc/backend/app/main.py                       ← 加 openapi_url 设置
```

---

## Group 1：标准文档 (Layer 4)

### Task 1：CODING_STANDARDS.md

**Files:**
- Create: `docs/CODING_STANDARDS.md`

- [ ] **Step 1：写文件**

```markdown
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
```

- [ ] **Step 2：提交**

```bash
git add docs/CODING_STANDARDS.md
git commit -m "docs: add CODING_STANDARDS.md"
```

---

### Task 2：TESTING_STANDARDS.md

**Files:**
- Create: `docs/TESTING_STANDARDS.md`

- [ ] **Step 1：写文件**

```markdown
# 测试规范

---

## 1. 框架选型

| 层 | 框架 | 备注 |
|----|------|------|
| 后端单元/集成 | pytest + httpx | httpx 提供 AsyncClient 测试 FastAPI |
| 后端 DB 集成 | testcontainers-python | 真实 PostgreSQL，不 mock DB |
| PC 单元 | Vitest + React Testing Library | 与 Vite 同源，速度快 |
| PC E2E | Playwright | 跑真实浏览器 |
| Android 单元 | JUnit 5 + MockK | |
| Android UI | Espresso | |

---

## 2. 目录结构

### 后端
```
poc/backend/
├── tests/
│   ├── conftest.py          ← pytest fixtures（DB session、app client）
│   ├── test_models.py       ← ORM 关系 / 约束测试
│   ├── test_schemas.py      ← Pydantic 验证测试
│   ├── api/
│   │   ├── test_cases.py    ← 案件 API 集成测试
│   │   ├── test_calls.py
│   │   └── test_users.py
│   └── services/
│       ├── test_asr.py
│       └── test_llm.py
```

### 前端
```
frontend/src/
└── __tests__/
    ├── pages/
    │   └── CasesPage.test.tsx
    └── components/
        └── CaseCard.test.tsx
```

---

## 3. 覆盖率目标

| 模块 | 行覆盖率目标 |
|------|------------|
| P0 模块（案件/通话/用户/配额）| ≥ 80% |
| 关键路径（拨打/上传/ASR/计费拦截）| ≥ 90% |
| 工具函数（加解密/脱敏/格式化）| ≥ 95% |
| P1 模块（结算/存证）| ≥ 60%（v1.1 提升）|

运行覆盖率报告：
```bash
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
```

---

## 4. Mock 约定

### 允许 mock 的场景
- 外部 HTTP 服务（DashScope ASR、DeepSeek LLM、推送服务）
- 时间（`datetime.now()`），用 `freezegun`
- 文件存储（MinIO），用 PoC 已有的 `storage_backend=local`

### 禁止 mock 的场景
- 数据库操作：必须用 testcontainers 启动真实 PostgreSQL
- 加密/脱敏函数：必须测真实输入输出

### dispatcher 复用模式
复用 `poc/backend/app/services/asr.py` 的 mock/real 切换模式。测试环境中设：
```python
# conftest.py
os.environ["ASR_BACKEND"] = "mock"
os.environ["LLM_BACKEND"] = "mock"
```

---

## 5. conftest.py 关键 fixture

```python
# poc/backend/tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from app.main import app
from app.core.db import get_db
from app.models.base import Base

@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest.fixture(scope="session")
def engine(pg_container):
    url = pg_container.get_connection_url().replace("psycopg2", "psycopg")
    eng = create_engine(url, future=True)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()

@pytest.fixture
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()

@pytest.fixture
async def client(db_session):
    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

---

## 6. CI 配置（见 .github/workflows/ci.yml）

PR 触发：
1. `ruff check` + `ruff format --check`
2. `mypy app/`
3. `pytest --cov=app --cov-fail-under=80`
4. `npm run lint` + `npm run typecheck` + `vitest run`

main 合并额外触发：
5. Playwright E2E（staging 环境）
```

- [ ] **Step 2：提交**

```bash
git add docs/TESTING_STANDARDS.md
git commit -m "docs: add TESTING_STANDARDS.md"
```

---

### Task 3：ACCEPTANCE.md

**Files:**
- Create: `docs/ACCEPTANCE.md`

- [ ] **Step 1：写文件**

```markdown
# 验收标准（ACCEPTANCE）

> 引用 `docs/DESIGN_SPEC.md` §6 性能基线和交付 checklist，本文档不重复，只扩展。

---

## 1. 通用完成定义（DoD）

任何功能进入"已完成"状态，必须同时满足：

| 维度 | 标准 |
|------|------|
| 功能 | PRD §21 对应页面的核心操作全部可用，无 501 Not Implemented |
| 测试 | 单元测试覆盖率达标（见 TESTING_STANDARDS.md §3）；关键路径 E2E 测试通过 |
| 视觉 | 与 HTML 原型（`ui/*.html`）一致；响应式在 1280px / 1440px / 1920px 下正常 |
| 可访问性 | 表单有 label；错误状态有文字说明；键盘可操作主要动作 |
| 性能 | 列表首屏 ≤ 1.5s（LCP）；API 响应 P90 ≤ 300ms（见 DESIGN_SPEC §6.2）|
| 安全 | 手机号脱敏；多租户隔离验证（跨租户请求返回 404/403）|

---

## 2. P0 页面验收一览

> 状态来自 `docs/UI_GAPS.md`（✅ UI 已完成 / ⚠️ 部分缺失 / ❌ 未实现）
> 每个页面的"完成条件"对应后端接口 + 前端页面双双落地。

### 角色 4：物业公司管理员（admin）

| 页面 | 核心验收条件 |
|------|------------|
| 管理看板（a-dashboard）| 今日外呼/接通/承诺缴费/实际回款4个指标实时更新；分钟用量/配额可见 |
| 案件列表（a-cases）| 支持状态/催收员/金额段筛选；分页；导出 Excel |
| 案件详情（a-case-detail）| 业主信息完整；活动时间线展示通话历史；工单/法务关联可点击 |
| 公海管理（a-pool）| 公海案件列表；批量分配给催收员；分配后从公海消失 |
| 名单导入（a-import）| Excel 上传；字段映射；重复检测；导入结果摘要 |
| 用户管理（a-users）| 创建内部员工；邀请外部兼职（生成链接）；停用恢复；批量导入 |
| 项目管理（a-projects）| 创建项目；指派物业侧负责人；项目状态可见 |

### 角色 5：主管/督导（supervisor）

| 页面 | 核心验收条件 |
|------|------------|
| 工作台（sv-workspace）| 实时通话状态看板；团队今日统计；分钟用量趋势 |
| 案件分配（sv-cases）| 批量分配；重新分配；优先级调整 |
| 通话复核（sv-review）| 抽查录音 + 转写；标注质量；AI 判断 vs 人工判断对比 |
| 升级案件处理（sv-escalated）| 升级案件列表；处理动作（转工单/转法务/关闭）|
| 团队绩效（sv-performance）| 接通率/承诺率/回款率排名 |

### 角色 6B：内部催收员（PC）

| 页面 | 核心验收条件 |
|------|------------|
| 通话工作台（my-workspace）| 三栏布局；AI 话术卡实时推送；风控干预可见；通话控制 |
| 我的案件（my-cases）| 私海列表；筛选；详情侧滑（案件信息 + 欠费明细 + 时间线）|
| 个人绩效（my-stats）| 本月通话/承诺/回款；本月通话分钟数 |

### 关键路径端到端验收

| 流程 | 验收条件 |
|------|---------|
| 欠费导入→分案→拨打→ASR→AI提示 | 全链路在测试环境一次跑通；录音上传成功；转写有内容；AI 推送出现 |
| 分钟配额超限拦截 | 将租户配额设为 1 分钟，发起第二个通话时返回 403 Quota Exceeded |
| 多租户隔离 | 用租户 A 的 token 请求租户 B 的案件返回 404 |
| 手机号脱敏 | API 响应的 phone 字段格式为 `138****1234`；数据库存储为密文 |

---

## 3. 不在验收范围的项（P1，v1.1）

- 服务商合作管理（a-partners）
- 数据报表（a-reports）
- 合规月报（a-compliance）
- 区块链存证集成
- 在线支付
- 撮合市场
```

- [ ] **Step 2：提交**

```bash
git add docs/ACCEPTANCE.md
git commit -m "docs: add ACCEPTANCE.md"
```

---

## Group 2：ORM 模型 + Alembic (Layer 2)

### Task 4：pyproject.toml + 测试环境

**Files:**
- Create: `poc/backend/pyproject.toml`
- Create: `poc/backend/.env.example`
- Create: `poc/backend/tests/__init__.py`
- Create: `poc/backend/tests/conftest.py`

- [ ] **Step 1：写 pyproject.toml**

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["app"]

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.coverage.run]
source = ["app"]
omit = ["app/models/__init__.py", "*/migrations/*"]
```

- [ ] **Step 2：写 .env.example**

```bash
# 复制为 .env 后填入真实值
DATABASE_URL=postgresql+psycopg://autoluyin:autoluyin_dev@localhost:25432/autoluyin

STORAGE_BACKEND=local
LOCAL_STORAGE_ROOT=/tmp/autoluyin_recordings
LOCAL_STORAGE_PUBLIC_BASE=http://localhost:18000
RECORDING_SIGN_SECRET=dev-secret-change-in-prod

ASR_BACKEND=mock
LLM_BACKEND=mock

DASHSCOPE_API_KEY=
LLM_API_KEY=sk-placeholder
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

- [ ] **Step 3：写 tests/conftest.py**（内容见 TESTING_STANDARDS.md §5，完整粘贴）

```python
import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

os.environ["ASR_BACKEND"] = "mock"
os.environ["LLM_BACKEND"] = "mock"

from app.main import app
from app.core.db import get_db
from app.models.base import Base


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def engine(pg_container):
    url = pg_container.get_connection_url().replace("psycopg2", "psycopg")
    eng = create_engine(url, future=True)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
async def client(db_session):
    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 4：安装测试依赖**

```bash
cd poc/backend
pip install pytest pytest-asyncio pytest-cov httpx testcontainers ruff mypy
```

- [ ] **Step 5：提交**

```bash
git add poc/backend/pyproject.toml poc/backend/.env.example poc/backend/tests/
git commit -m "chore(backend): add pyproject.toml, .env.example, test skeleton"
```

---

### Task 5：SQLAlchemy ORM 模型

**Files:**
- Create: `poc/backend/app/models/base.py`
- Create: `poc/backend/app/models/tenant.py`
- Create: `poc/backend/app/models/user.py`
- Create: `poc/backend/app/models/case.py`
- Create: `poc/backend/app/models/call.py`
- Create: `poc/backend/app/models/work.py`
- Create: `poc/backend/app/models/settlement.py`
- Modify: `poc/backend/app/models/__init__.py`

- [ ] **Step 1：写 models/base.py**

```python
from sqlalchemy.orm import DeclarativeBase, MappedColumn
from sqlalchemy import DateTime, func
from datetime import datetime
import sqlalchemy as sa


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: MappedColumn[datetime] = sa.orm.mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: MappedColumn[datetime] = sa.orm.mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )
```

- [ ] **Step 2：写 models/tenant.py**

```python
from __future__ import annotations
from typing import Optional
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenant"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    credit_code: Mapped[Optional[str]] = mapped_column(sa.Text, unique=True)
    admin_phone_enc: Mapped[str] = mapped_column(sa.Text, nullable=False)  # AES-256
    plan: Mapped[str] = mapped_column(sa.Text, nullable=False, default="trial")
    expires_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    monthly_minute_quota: Mapped[Optional[int]] = mapped_column(sa.Integer)
    minute_quota_updated_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)

    memberships: Mapped[list[UserTenantMembership]] = relationship(back_populates="tenant")


class ServiceProvider(Base, TimestampMixin):
    __tablename__ = "service_provider"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    provider_type: Mapped[str] = mapped_column(
        sa.Text, nullable=False
    )  # legal / collection / both
    admin_phone_enc: Mapped[str] = mapped_column(sa.Text, nullable=False)
    monthly_minute_quota: Mapped[Optional[int]] = mapped_column(sa.Integer)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)


class ProviderTenantContract(Base, TimestampMixin):
    __tablename__ = "provider_tenant_contract"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False)
    provider_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("service_provider.id"), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    service_types: Mapped[list[str]] = mapped_column(sa.ARRAY(sa.Text), nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="active")


class TenantMinuteUsage(Base):
    __tablename__ = "tenant_minute_usage"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False)
    year_month: Mapped[str] = mapped_column(sa.Text, nullable=False)  # "2026-04"
    used_minutes: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    quota_at_time: Mapped[Optional[int]] = mapped_column(sa.Integer)

    __table_args__ = (sa.UniqueConstraint("tenant_id", "year_month"),)


class UserTenantMembership(Base, TimestampMixin):
    __tablename__ = "user_tenant_membership"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False)
    role: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_type: Mapped[str] = mapped_column(sa.Text, nullable=False, default="INTERNAL")
    provider_id: Mapped[Optional[int]] = mapped_column(sa.BigInteger, sa.ForeignKey("service_provider.id"))
    quota: Mapped[Optional[int]] = mapped_column(sa.Integer)
    expire_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    access_hours: Mapped[Optional[str]] = mapped_column(sa.Text)  # "09:00-18:00"
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)

    tenant: Mapped[Tenant] = relationship(back_populates="memberships")
```

- [ ] **Step 3：写 models/user.py**

```python
from __future__ import annotations
from typing import Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin


class UserAccount(Base, TimestampMixin):
    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    phone_enc: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)  # AES-256
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    last_login_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))


class PlatformOpsAssignment(Base, TimestampMixin):
    __tablename__ = "platform_ops_assignment"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    ops_user_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(sa.Text, nullable=False)  # tenant / provider
    entity_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)
```

- [ ] **Step 4：写 models/case.py**

```python
from __future__ import annotations
from typing import Optional
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin


class OwnerProfile(Base, TimestampMixin):
    __tablename__ = "owner_profile"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    phone_enc: Mapped[str] = mapped_column(sa.Text, nullable=False)  # AES-256
    data_hash: Mapped[Optional[str]] = mapped_column(sa.Text)  # SHA-256 防篡改预埋
    building: Mapped[Optional[str]] = mapped_column(sa.Text)
    room: Mapped[Optional[str]] = mapped_column(sa.Text)
    tags: Mapped[list[str]] = mapped_column(sa.ARRAY(sa.Text), default=list)
    do_not_call: Mapped[bool] = mapped_column(sa.Boolean, default=False)


class Project(Base, TimestampMixin):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    project_type: Mapped[str] = mapped_column(sa.Text, nullable=False)  # collection / vote
    provider_id: Mapped[Optional[int]] = mapped_column(sa.BigInteger, sa.ForeignKey("service_provider.id"))
    property_pm_user_id: Mapped[Optional[int]] = mapped_column(sa.BigInteger, sa.ForeignKey("user_account.id"))
    provider_pm_user_id: Mapped[Optional[int]] = mapped_column(sa.BigInteger, sa.ForeignKey("user_account.id"))
    plan_start: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    plan_end: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="active")
    description: Mapped[Optional[str]] = mapped_column(sa.Text)


class CollectionCase(Base, TimestampMixin):
    __tablename__ = "collection_case"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False)
    project_id: Mapped[Optional[int]] = mapped_column(sa.BigInteger, sa.ForeignKey("project.id"))
    owner_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("owner_profile.id"), nullable=False)
    assigned_to: Mapped[Optional[int]] = mapped_column(sa.BigInteger, sa.ForeignKey("user_account.id"))
    pool_type: Mapped[str] = mapped_column(sa.Text, nullable=False, default="public")  # public / private
    stage: Mapped[str] = mapped_column(sa.Text, nullable=False, default="new")
    amount_owed: Mapped[Optional[sa.Numeric]] = mapped_column(sa.Numeric(12, 2))
    months_overdue: Mapped[Optional[int]] = mapped_column(sa.Integer)
    priority_score: Mapped[int] = mapped_column(sa.Integer, default=0)
    last_contact_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    monthly_contact_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    data_hash: Mapped[Optional[str]] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="active")

    __table_args__ = (
        sa.Index("idx_case_tenant_pool", "tenant_id", "pool_type"),
        sa.Index("idx_case_tenant_assigned", "tenant_id", "assigned_to"),
    )
```

- [ ] **Step 5：写 models/call.py**

```python
from __future__ import annotations
from typing import Optional
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin


class CallRecord(Base, TimestampMixin):
    __tablename__ = "call_record"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False)
    case_id: Mapped[Optional[int]] = mapped_column(sa.BigInteger, sa.ForeignKey("collection_case.id"))
    caller_user_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False)
    callee_phone_enc: Mapped[str] = mapped_column(sa.Text, nullable=False)
    initiated_by: Mapped[str] = mapped_column(sa.Text, nullable=False, default="app")  # app / pc
    started_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    ended_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    duration_sec: Mapped[Optional[int]] = mapped_column(sa.Integer)
    billable_duration: Mapped[Optional[int]] = mapped_column(sa.Integer)  # 接通后时长（秒）
    result_tag: Mapped[Optional[str]] = mapped_column(sa.Text)
    emotion_tag: Mapped[Optional[str]] = mapped_column(sa.Text)
    risk_flagged: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    recording_url: Mapped[Optional[str]] = mapped_column(sa.Text)
    data_hash: Mapped[Optional[str]] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="pending")

    __table_args__ = (
        sa.Index("idx_callrecord_tenant", "tenant_id"),
        sa.Index("idx_callrecord_case", "case_id"),
    )


class Transcript(Base, TimestampMixin):
    __tablename__ = "transcript"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    call_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("call_record.id"), nullable=False)
    full_text: Mapped[Optional[str]] = mapped_column(sa.Text)
    segments: Mapped[Optional[dict]] = mapped_column(sa.JSON)  # [{speaker, start_ms, end_ms, text}]
    asr_model: Mapped[Optional[str]] = mapped_column(sa.Text)
    data_hash: Mapped[Optional[str]] = mapped_column(sa.Text)


class AnalysisResult(Base, TimestampMixin):
    __tablename__ = "analysis_result"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    call_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("call_record.id"), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(sa.Text)
    key_segments: Mapped[Optional[dict]] = mapped_column(sa.JSON)
    followup_suggestion: Mapped[Optional[str]] = mapped_column(sa.Text)
    prompt_version: Mapped[Optional[str]] = mapped_column(sa.Text)
    llm_model: Mapped[Optional[str]] = mapped_column(sa.Text)
    needs_review: Mapped[bool] = mapped_column(sa.Boolean, default=False)


class RiskEvent(Base, TimestampMixin):
    __tablename__ = "risk_event"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    call_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("call_record.id"), nullable=False)
    level: Mapped[str] = mapped_column(sa.Text, nullable=False)  # L1 / L2 / L3
    category: Mapped[str] = mapped_column(sa.Text, nullable=False)
    trigger_text: Mapped[Optional[str]] = mapped_column(sa.Text)
    audio_offset_ms: Mapped[Optional[int]] = mapped_column(sa.Integer)
    intervention: Mapped[str] = mapped_column(sa.Text, nullable=False)  # warn / interrupt / terminate
    data_hash: Mapped[Optional[str]] = mapped_column(sa.Text)
```

- [ ] **Step 6：写 models/work.py**

```python
from __future__ import annotations
from typing import Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin


class WorkOrder(Base, TimestampMixin):
    __tablename__ = "work_order"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False)
    case_id: Mapped[Optional[int]] = mapped_column(sa.BigInteger, sa.ForeignKey("collection_case.id"))
    call_id: Mapped[Optional[int]] = mapped_column(sa.BigInteger, sa.ForeignKey("call_record.id"))
    order_type: Mapped[str] = mapped_column(sa.Text, nullable=False)  # quality / reduction / dispute / other
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    assigned_to: Mapped[Optional[int]] = mapped_column(sa.BigInteger, sa.ForeignKey("user_account.id"))
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="open")
    resolution: Mapped[Optional[str]] = mapped_column(sa.Text)


class LegalCase(Base, TimestampMixin):
    __tablename__ = "legal_case"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False)
    case_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("collection_case.id"), nullable=False)
    stage: Mapped[str] = mapped_column(sa.Text, nullable=False, default="pending_eval")
    amount_disputed: Mapped[Optional[sa.Numeric]] = mapped_column(sa.Numeric(12, 2))
    lawyer_name: Mapped[Optional[str]] = mapped_column(sa.Text)
    law_firm: Mapped[Optional[str]] = mapped_column(sa.Text)
    next_milestone: Mapped[Optional[str]] = mapped_column(sa.Text)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)
```

- [ ] **Step 7：写 models/settlement.py**

```python
from __future__ import annotations
from typing import Optional
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin


class SettlementStatement(Base, TimestampMixin):
    __tablename__ = "settlement_statement"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    contract_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("provider_tenant_contract.id"), nullable=False)
    period_start: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    total_amount: Mapped[sa.Numeric] = mapped_column(sa.Numeric(12, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="DRAFT")  # DRAFT/CONFIRMED/PAID/DISPUTED

    __table_args__ = (
        sa.CheckConstraint("status IN ('DRAFT','CONFIRMED','PAID','DISPUTED')", name="ck_settlement_status"),
    )


class DisputeRecord(Base, TimestampMixin):
    __tablename__ = "dispute_record"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    statement_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("settlement_statement.id"), nullable=False)
    reason: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, default="open")
    resolution: Mapped[Optional[str]] = mapped_column(sa.Text)
    submitted_by: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False)
```

- [ ] **Step 8：写 models/__init__.py**

```python
from .base import Base
from .tenant import Tenant, ServiceProvider, ProviderTenantContract, TenantMinuteUsage, UserTenantMembership
from .user import UserAccount, PlatformOpsAssignment
from .case import OwnerProfile, Project, CollectionCase
from .call import CallRecord, Transcript, AnalysisResult, RiskEvent
from .work import WorkOrder, LegalCase
from .settlement import SettlementStatement, DisputeRecord

__all__ = [
    "Base",
    "Tenant", "ServiceProvider", "ProviderTenantContract", "TenantMinuteUsage", "UserTenantMembership",
    "UserAccount", "PlatformOpsAssignment",
    "OwnerProfile", "Project", "CollectionCase",
    "CallRecord", "Transcript", "AnalysisResult", "RiskEvent",
    "WorkOrder", "LegalCase",
    "SettlementStatement", "DisputeRecord",
]
```

- [ ] **Step 9：写测试 tests/test_models.py**

```python
import pytest
from sqlalchemy import text
from app.models import Base, Tenant, UserAccount, CollectionCase, OwnerProfile


def test_tables_created(engine):
    """All expected tables exist after metadata.create_all"""
    expected = {
        "tenant", "service_provider", "provider_tenant_contract",
        "tenant_minute_usage", "user_tenant_membership",
        "user_account", "platform_ops_assignment",
        "owner_profile", "project", "collection_case",
        "call_record", "transcript", "analysis_result", "risk_event",
        "work_order", "legal_case",
        "settlement_statement", "dispute_record",
    }
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        ))
        actual = {row[0] for row in result}
    assert expected.issubset(actual), f"Missing tables: {expected - actual}"


def test_tenant_creation(db_session):
    tenant = Tenant(
        name="测试物业",
        admin_phone_enc="encrypted_phone",
        plan="basic",
        monthly_minute_quota=1000,
    )
    db_session.add(tenant)
    db_session.flush()
    assert tenant.id is not None
    assert tenant.is_active is True


def test_case_requires_tenant_id(db_session):
    """CollectionCase without tenant_id should raise IntegrityError"""
    from sqlalchemy.exc import IntegrityError
    case = CollectionCase(owner_id=1)  # no tenant_id
    db_session.add(case)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_tenant_minute_usage_unique_per_month(db_session, engine):
    from app.models.tenant import TenantMinuteUsage
    tenant = Tenant(name="配额测试", admin_phone_enc="enc", plan="basic")
    db_session.add(tenant)
    db_session.flush()

    u1 = TenantMinuteUsage(tenant_id=tenant.id, year_month="2026-04", used_minutes=100)
    u2 = TenantMinuteUsage(tenant_id=tenant.id, year_month="2026-04", used_minutes=200)
    db_session.add(u1)
    db_session.flush()
    db_session.add(u2)
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db_session.flush()
```

- [ ] **Step 10：跑测试（RED 阶段，表还不存在）**

```bash
cd poc/backend
pytest tests/test_models.py -v
# 预期：FAIL — engine fixture 报 ImportError 或 table not found
```

- [ ] **Step 11：提交模型文件**

```bash
git add poc/backend/app/models/ poc/backend/tests/test_models.py
git commit -m "feat(models): add SQLAlchemy ORM models for all entities"
```

- [ ] **Step 12：跑测试（GREEN 阶段）**

```bash
pytest tests/test_models.py -v
# 预期：PASS — 所有表创建成功，约束测试通过
```

---

### Task 6：Alembic 迁移

**Files:**
- Create: `poc/backend/alembic.ini`
- Create: `poc/backend/alembic/env.py`
- Create: `poc/backend/alembic/versions/0001_initial.py`

- [ ] **Step 1：安装 alembic**

```bash
cd poc/backend
pip install alembic
alembic init alembic
```

- [ ] **Step 2：更新 alembic/env.py（替换 target_metadata）**

```python
# alembic/env.py 关键修改（其余保持 alembic init 生成的默认）
from app.models.base import Base  # noqa: F401
import app.models  # noqa: F401 — 确保所有模型被 import
from app.core.config import settings

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

- [ ] **Step 3：生成初始迁移**

```bash
alembic revision --autogenerate -m "initial schema"
# 检查生成的 alembic/versions/xxxx_initial_schema.py：
# upgrade() 应包含所有 create_table 调用
```

- [ ] **Step 4：更新 docker-compose.yml，加 alembic upgrade**

在 `poc/docker-compose.yml` 的 `backend` service 中，把 command 改为：

```yaml
command: >
  sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
```

- [ ] **Step 5：提交**

```bash
git add poc/backend/alembic/ poc/backend/alembic.ini poc/docker-compose.yml
git commit -m "feat(db): add Alembic migration setup with initial schema"
```

---

## Group 3：Pydantic Schemas + OpenAPI (Layer 1)

### Task 7：公共 Schema

**Files:**
- Create: `poc/backend/app/schemas/common.py`
- Create: `poc/backend/app/schemas/__init__.py`

- [ ] **Step 1：写 schemas/common.py**

```python
from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class PaginationQuery(BaseModel):
    page: int = 1
    page_size: int = 20

    model_config = ConfigDict(str_strip_whitespace=True)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class ErrorDetail(BaseModel):
    code: str
    message: str
```

- [ ] **Step 2：写 schemas/case.py**

```python
from typing import Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class CaseListQuery(PaginationQuery):
    status: Optional[str] = None
    pool_type: Optional[str] = None
    assigned_to: Optional[int] = None
    keyword: Optional[str] = None


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    project_id: Optional[int]
    owner_id: int
    assigned_to: Optional[int]
    pool_type: str
    stage: str
    amount_owed: Optional[Decimal]
    months_overdue: Optional[int]
    priority_score: int
    last_contact_at: Optional[datetime]
    monthly_contact_count: int
    status: str
    created_at: datetime
    updated_at: datetime


class CaseAssignRequest(BaseModel):
    case_ids: list[int] = Field(..., min_length=1, max_length=500)
    assign_to: int


class CaseImportRow(BaseModel):
    name: str = Field(..., min_length=1)
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    building: Optional[str] = None
    room: Optional[str] = None
    amount_owed: Optional[Decimal] = None
    months_overdue: Optional[int] = None
```

- [ ] **Step 3：写 schemas/call.py**

```python
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from .common import PaginationQuery


class CallListQuery(PaginationQuery):
    case_id: Optional[int] = None
    status: Optional[str] = None


class CallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    case_id: Optional[int]
    initiated_by: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_sec: Optional[int]
    billable_duration: Optional[int]
    result_tag: Optional[str]
    risk_flagged: bool
    status: str
    created_at: datetime


class CallMinuteQuotaStatus(BaseModel):
    tenant_id: int
    year_month: str
    used_minutes: int
    quota: Optional[int]
    remaining: Optional[int]
    pct_used: Optional[float]
    is_exhausted: bool
```

- [ ] **Step 4：写 schemas/user.py**

```python
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class UserCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    role: str
    supervisor_id: Optional[int] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone_masked: str  # 138****1234，service 层计算
    role: str
    is_active: bool
    created_at: datetime


class InviteLinkRequest(BaseModel):
    role: str = "agent_external"
    quota: int = Field(20, ge=1, le=200)
    expire_days: int = Field(30, ge=1, le=90)
    access_hours: Optional[str] = "09:00-18:00"


class InviteLinkResponse(BaseModel):
    token: str
    url: str
    expires_at: datetime
```

- [ ] **Step 5：写 schemas 测试**

```python
# tests/test_schemas.py
import pytest
from decimal import Decimal
from app.schemas.case import CaseImportRow
from app.schemas.user import UserCreateRequest
from app.schemas.call import CallMinuteQuotaStatus


def test_case_import_valid_phone():
    row = CaseImportRow(name="张三", phone="13800138001", amount_owed=Decimal("1200"))
    assert row.phone == "13800138001"


def test_case_import_invalid_phone():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CaseImportRow(name="张三", phone="12345")


def test_user_create_strips_whitespace():
    req = UserCreateRequest(name="  李四  ", phone="13900139001", role="agent_internal")
    assert req.name == "李四"


def test_quota_exhausted_flag():
    status = CallMinuteQuotaStatus(
        tenant_id=1, year_month="2026-04",
        used_minutes=100, quota=100, remaining=0,
        pct_used=1.0, is_exhausted=True
    )
    assert status.is_exhausted is True


def test_quota_no_limit():
    status = CallMinuteQuotaStatus(
        tenant_id=1, year_month="2026-04",
        used_minutes=500, quota=None, remaining=None,
        pct_used=None, is_exhausted=False
    )
    assert status.quota is None
    assert not status.is_exhausted
```

- [ ] **Step 6：跑 schema 测试**

```bash
pytest tests/test_schemas.py -v
# 预期：PASS — 5 个测试全通过
```

- [ ] **Step 7：更新 main.py（暴露 OpenAPI）**

在 `poc/backend/app/main.py` 中修改 FastAPI 实例化：

```python
app = FastAPI(
    title="有证慧催 API",
    version="0.1.0",
    description="autoluyin MVP backend",
    openapi_url="/api/openapi.json",   # 明确路径，Refine.dev 要用
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)
```

- [ ] **Step 8：提交**

```bash
git add poc/backend/app/schemas/ poc/backend/tests/test_schemas.py poc/backend/app/main.py
git commit -m "feat(schemas): add Pydantic v2 schemas for case/call/user + OpenAPI config"
```

---

## Group 4：工程脚手架 (Layer 3)

### Task 8：后端工具链配置

**Files:**
- Modify: `poc/backend/requirements.txt`（追加开发依赖）

- [ ] **Step 1：更新 requirements.txt，追加开发/测试依赖**

在现有 requirements.txt 末尾追加：

```
# dev / test
pytest==8.3.4
pytest-asyncio==0.24.0
pytest-cov==6.0.0
httpx==0.27.2
testcontainers==4.8.1
ruff==0.8.0
mypy==1.13.0
alembic==1.14.0
freezegun==1.5.1
```

- [ ] **Step 2：验证 ruff 跑通**

```bash
cd poc/backend
ruff check app/
# 预期：若有 lint 错误则修复，最终 0 errors
```

- [ ] **Step 3：提交**

```bash
git add poc/backend/requirements.txt
git commit -m "chore(backend): update requirements with dev/test deps"
```

---

### Task 9：前端项目初始化

**Files:**
- Create: `frontend/` 目录（Vite + React + Refine.dev + shadcn/ui）

- [ ] **Step 1：创建 Vite + React + TypeScript 项目**

```bash
cd /Users/shuo/AI/autoluyin
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

- [ ] **Step 2：安装 Refine.dev + shadcn/ui + 相关依赖**

```bash
npm install @refinedev/core @refinedev/react-router @refinedev/simple-rest
npm install @refinedev/shadcn-ui
npm install react-router-dom
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npx shadcn-ui@latest init
# shadcn init 选项：TypeScript=yes, style=default, base color=slate, CSS variables=yes
```

- [ ] **Step 3：安装图标和工具库**

```bash
npm install lucide-react
npm install -D @typescript-eslint/eslint-plugin @typescript-eslint/parser eslint prettier
```

- [ ] **Step 4：写 .eslintrc.json**

```json
{
  "root": true,
  "parser": "@typescript-eslint/parser",
  "plugins": ["@typescript-eslint"],
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:@typescript-eslint/recommended-requiring-type-checking"
  ],
  "parserOptions": {
    "project": "./tsconfig.json"
  },
  "rules": {
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/no-unused-vars": ["error", { "argsIgnorePattern": "^_" }],
    "no-console": ["warn", { "allow": ["warn", "error"] }]
  }
}
```

- [ ] **Step 5：写 prettier.config.js**

```js
/** @type {import('prettier').Config} */
export default {
  semi: true,
  singleQuote: false,
  trailingComma: "all",
  printWidth: 100,
  tabWidth: 2,
};
```

- [ ] **Step 6：写 src/providers/index.tsx（Refine dataProvider 骨架）**

```tsx
import { DataProvider } from "@refinedev/core";
import { simpleRestDataProvider } from "@refinedev/simple-rest";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:18000";

export const dataProvider: DataProvider = simpleRestDataProvider(
  `${API_BASE}/api/v1`
);
```

- [ ] **Step 7：写 src/App.tsx（Refine 骨架）**

```tsx
import { Refine } from "@refinedev/core";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { dataProvider } from "./providers";

function App() {
  return (
    <BrowserRouter>
      <Refine dataProvider={dataProvider}>
        <Routes>
          <Route path="/" element={<div>有证慧催 MVP</div>} />
        </Routes>
      </Refine>
    </BrowserRouter>
  );
}

export default App;
```

- [ ] **Step 8：更新 package.json scripts**

```json
"scripts": {
  "dev": "vite",
  "build": "tsc && vite build",
  "lint": "eslint src --ext .ts,.tsx",
  "format": "prettier --write src/",
  "typecheck": "tsc --noEmit",
  "test": "vitest run",
  "test:ui": "vitest --ui"
}
```

- [ ] **Step 9：验证前端可以启动**

```bash
npm run dev
# 浏览器打开 http://localhost:5173 → 应看到"有证慧催 MVP"
```

- [ ] **Step 10：提交**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Vite + React + Refine.dev + shadcn/ui project"
```

---

## Group 5：CI (Layer 5)

### Task 10：GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1：写 ci.yml**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend-lint:
    name: Backend Lint & Typecheck
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: poc/backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff mypy pydantic
      - run: ruff check app/
      - run: ruff format --check app/
      - run: mypy app/

  backend-test:
    name: Backend Tests
    runs-on: ubuntu-latest
    needs: backend-lint
    defaults:
      run:
        working-directory: poc/backend
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: autoluyin
          POSTGRES_PASSWORD: autoluyin_dev
          POSTGRES_DB: autoluyin_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: pytest --cov=app --cov-report=xml --cov-fail-under=80
        env:
          DATABASE_URL: postgresql+psycopg://autoluyin:autoluyin_dev@localhost:5432/autoluyin_test
          ASR_BACKEND: mock
          LLM_BACKEND: mock
          STORAGE_BACKEND: local
          LOCAL_STORAGE_ROOT: /tmp/recordings
          RECORDING_SIGN_SECRET: ci-secret
      - uses: codecov/codecov-action@v4
        with:
          file: poc/backend/coverage.xml

  frontend-lint:
    name: Frontend Lint & Typecheck
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck

  frontend-build:
    name: Frontend Build
    runs-on: ubuntu-latest
    needs: frontend-lint
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run build
        env:
          VITE_API_BASE: http://localhost:18000
```

- [ ] **Step 2：提交**

```bash
git add .github/
git commit -m "ci: add GitHub Actions CI for backend lint/test and frontend lint/build"
```

---

## 完成验证

全部 10 个 Task 完成后，运行以下检查：

```bash
# 后端
cd poc/backend
ruff check app/ && echo "✅ ruff OK"
mypy app/ && echo "✅ mypy OK"
pytest tests/ -v --cov=app --cov-fail-under=80 && echo "✅ tests OK"

# 前端
cd ../../frontend
npm run lint && echo "✅ eslint OK"
npm run typecheck && echo "✅ tsc OK"
npm run build && echo "✅ build OK"

# 文档
ls ../docs/CODING_STANDARDS.md ../docs/TESTING_STANDARDS.md ../docs/ACCEPTANCE.md && echo "✅ docs OK"

# CI
ls ../.github/workflows/ci.yml && echo "✅ CI OK"
```

所有行都输出 ✅ 后，Stage D 完成，可以进入 Stage E（MVP 业务编码）。
