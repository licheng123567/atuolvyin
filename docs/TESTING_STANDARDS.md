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
