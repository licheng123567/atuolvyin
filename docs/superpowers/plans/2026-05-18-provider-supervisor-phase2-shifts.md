# 服务商督导工作台 Phase 2 — 值班排班 scope-aware 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把值班排班的 4 个 `/supervisor/shifts` 端点改成 scope-aware —— 服务商督导只管本服务商排班，与物业督导隔离。

**Architecture:** `SupervisorShift` / `SupervisorShiftSwapRequest` 两表加可空 `provider_id`（`NULL`=物业、非空=服务商）；`SupervisorShift` 旧唯一约束换成两个 partial unique index（物业/服务商各一）。4 端点守卫 `require_tenant_roles`→`require_roles`、注入 Phase 1 的 `supervisor_scope`，所有读写按 `provider_id` 过滤。前端 nav 补「值班排班」。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + PostgreSQL（后端）；React + TypeScript（前端 nav）；pytest + testcontainers / Vitest（测试）。

设计依据：`docs/superpowers/specs/2026-05-18-provider-supervisor-phase2-shifts-design.md`。

**关键事实（实现前必读）：**
- 测试 conftest（`poc/backend/tests/conftest.py:30`）用 `Base.metadata.create_all(eng)` 建表 —— **模型 `__table_args__` 是测试的事实源**，Alembic 迁移只作用于真实/dev DB。两者必须一致。
- provider 表名是 `service_provider`（不是 `provider`）；FK 目标 `service_provider.id`。
- 当前 Alembic head 是 `24018v220d`。
- `supervisor_shift` 表已有 `supervisor_user_id` 列但代码从不写入 —— 本计划不动它。
- Phase 1 共享件 `poc/backend/app/api/_supervisor_scope.py` 已有 `SupervisorScope` 与 `supervisor_scope`（FastAPI 依赖：解析 token，`tenant_id` 缺失或 `provider_id<=0` → 403 `ERR_NO_SCOPE`）。
- 当前 `supervisor_shift` 端点**零测试覆盖**（`tests/` 下无 shift 测试文件）。

---

## 文件结构

| 文件 | 职责 | 本计划动作 |
|------|------|-----------|
| `poc/backend/app/models/supervisor_shift.py` | `SupervisorShift` / `SupervisorShiftSwapRequest` ORM | 改：两表加 `provider_id`；`SupervisorShift` 唯一约束换 partial unique index |
| `poc/backend/alembic/versions/24019_v220_supervisor_shift_provider_scope.py` | 迁移脚本 | 新建 |
| `poc/backend/app/api/supervisor_shifts.py` | 4 个排班端点 | 改：守卫 + scope 过滤；新增局部 helper `_shift_scope_clause` |
| `poc/backend/tests/api/test_supervisor_shift_model.py` | 模型层 partial unique 行为测试 | 新建（Task 1） |
| `poc/backend/tests/api/test_supervisor_shifts_list_scope.py` | `GET /shifts` 隔离测试 | 新建（Task 2） |
| `poc/backend/tests/api/test_supervisor_shifts_save_scope.py` | `POST /shifts` 隔离测试 | 新建（Task 3） |
| `poc/backend/tests/api/test_supervisor_shifts_swap_scope.py` | swap 两端点隔离测试 | 新建（Task 4） |
| `frontend/src/config/nav.ts` | 督导 nav | 改：`SUPERVISOR_PROVIDER_NAV` 加值班排班 |
| `frontend/src/config/__tests__/nav.test.ts` | nav 单测 | 改：补断言 |

---

## Task 1: 数据模型迁移 — 两表加 `provider_id` + 换唯一约束

**Files:**
- Modify: `poc/backend/app/models/supervisor_shift.py`
- Create: `poc/backend/alembic/versions/24019_v220_supervisor_shift_provider_scope.py`
- Test: `poc/backend/tests/api/test_supervisor_shift_model.py`

- [ ] **Step 1: 写失败测试** — 创建 `poc/backend/tests/api/test_supervisor_shift_model.py`：

```python
"""Phase 2 — SupervisorShift partial unique index 行为测试。

物业侧（provider_id IS NULL）与服务商侧（provider_id 非空）的排班
互不冲突；同一 scope 内同 (tenant, date, slot) 重复则被唯一索引拒绝。
"""
from __future__ import annotations

from datetime import date

import pytest
import sqlalchemy as sa

from app.models.supervisor_shift import SupervisorShift


def _shift(tenant_id: int, provider_id: int | None, slot: str = "morning") -> SupervisorShift:
    return SupervisorShift(
        tenant_id=tenant_id,
        provider_id=provider_id,
        shift_date=date(2026, 6, 1),
        slot=slot,
        supervisor_name="督导甲",
    )


def test_property_and_provider_same_slot_coexist(db_session):
    """同 (tenant, date, slot)：物业排班 + 服务商 A 排班 + 服务商 B 排班 可并存。"""
    db_session.add_all([
        _shift(1, None),
        _shift(1, 100),
        _shift(1, 200),
    ])
    db_session.flush()
    rows = db_session.execute(
        sa.select(SupervisorShift).where(SupervisorShift.tenant_id == 1)
    ).scalars().all()
    assert len(rows) == 3


def test_duplicate_property_slot_rejected(db_session):
    """物业侧同 (tenant, date, slot) 重复 → partial unique index 拒绝。"""
    db_session.add(_shift(1, None))
    db_session.flush()
    db_session.add(_shift(1, None))
    with pytest.raises(sa.exc.IntegrityError):
        db_session.flush()


def test_duplicate_provider_slot_rejected(db_session):
    """服务商侧同 (tenant, provider, date, slot) 重复 → partial unique index 拒绝。"""
    db_session.add(_shift(1, 100))
    db_session.flush()
    db_session.add(_shift(1, 100))
    with pytest.raises(sa.exc.IntegrityError):
        db_session.flush()
```

> `db_session` 是 `tests/conftest.py` 已有的 fixture（testcontainers PG + 事务回滚）。如名称不同，先 `grep -n "def db_session\|def session" tests/conftest.py` 对齐。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_supervisor_shift_model.py -q`
Expected: FAIL —— `SupervisorShift` 无 `provider_id` 参数（`TypeError`）。

- [ ] **Step 3: 改模型** —— `poc/backend/app/models/supervisor_shift.py`。

`SupervisorShift` 类：在 `supervisor_name` 字段后加 `provider_id` 字段：

```python
    provider_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("service_provider.id", ondelete="CASCADE"),
    )
```

把 `SupervisorShift.__table_args__` 整体替换为（删掉 `UniqueConstraint`，换成两个 partial unique `Index`，新增 provider_id 索引）：

```python
    __table_args__ = (
        sa.CheckConstraint(
            "slot IN ('morning', 'afternoon', 'evening')",
            name="ck_supervisor_shift_slot",
        ),
        sa.Index("ix_supervisor_shift_tenant_date", "tenant_id", "shift_date"),
        sa.Index("ix_supervisor_shift_provider_id", "provider_id"),
        # 物业侧（provider_id IS NULL）唯一：tenant + date + slot
        sa.Index(
            "uq_supervisor_shift_property",
            "tenant_id", "shift_date", "slot",
            unique=True,
            postgresql_where=sa.text("provider_id IS NULL"),
        ),
        # 服务商侧（provider_id 非空）唯一：tenant + provider + date + slot
        sa.Index(
            "uq_supervisor_shift_provider",
            "tenant_id", "provider_id", "shift_date", "slot",
            unique=True,
            postgresql_where=sa.text("provider_id IS NOT NULL"),
        ),
    )
```

`SupervisorShiftSwapRequest` 类：在 `status` 字段后加同款 `provider_id` 字段：

```python
    provider_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("service_provider.id", ondelete="CASCADE"),
    )
```

把 `SupervisorShiftSwapRequest.__table_args__` 替换为（保留两个 CheckConstraint，加 provider_id 索引）：

```python
    __table_args__ = (
        sa.CheckConstraint(
            "slot IN ('morning', 'afternoon', 'evening')",
            name="ck_swap_request_slot",
        ),
        sa.CheckConstraint(
            "status IN ('pending_confirm', 'accepted', 'rejected', 'cancelled')",
            name="ck_swap_request_status",
        ),
        sa.Index("ix_supervisor_shift_swap_request_provider_id", "provider_id"),
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_supervisor_shift_model.py -q`
Expected: PASS（3 passed）。

- [ ] **Step 5: 写 Alembic 迁移** —— 创建 `poc/backend/alembic/versions/24019_v220_supervisor_shift_provider_scope.py`：

```python
"""Phase 2 — supervisor_shift / swap_request 加 provider_id + 换唯一约束

Revision ID: 24019v220e
Revises: 24018v220d
Create Date: 2026-05-18 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24019v220e"
down_revision: str | None = "24018v220d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 两表加 provider_id（NULL=物业 / 非NULL=服务商）
    op.add_column("supervisor_shift", sa.Column("provider_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_supervisor_shift_provider",
        "supervisor_shift", "service_provider",
        ["provider_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_supervisor_shift_provider_id", "supervisor_shift", ["provider_id"])

    op.add_column(
        "supervisor_shift_swap_request",
        sa.Column("provider_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_supervisor_shift_swap_request_provider",
        "supervisor_shift_swap_request", "service_provider",
        ["provider_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index(
        "ix_supervisor_shift_swap_request_provider_id",
        "supervisor_shift_swap_request", ["provider_id"],
    )

    # SupervisorShift 旧唯一约束 → 两个 partial unique index
    op.drop_constraint("uq_supervisor_shift_tenant_date_slot", "supervisor_shift", type_="unique")
    op.create_index(
        "uq_supervisor_shift_property",
        "supervisor_shift", ["tenant_id", "shift_date", "slot"],
        unique=True, postgresql_where=sa.text("provider_id IS NULL"),
    )
    op.create_index(
        "uq_supervisor_shift_provider",
        "supervisor_shift", ["tenant_id", "provider_id", "shift_date", "slot"],
        unique=True, postgresql_where=sa.text("provider_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_supervisor_shift_provider", table_name="supervisor_shift")
    op.drop_index("uq_supervisor_shift_property", table_name="supervisor_shift")
    op.create_unique_constraint(
        "uq_supervisor_shift_tenant_date_slot",
        "supervisor_shift", ["tenant_id", "shift_date", "slot"],
    )
    op.drop_index(
        "ix_supervisor_shift_swap_request_provider_id",
        table_name="supervisor_shift_swap_request",
    )
    op.drop_constraint(
        "fk_supervisor_shift_swap_request_provider",
        "supervisor_shift_swap_request", type_="foreignkey",
    )
    op.drop_column("supervisor_shift_swap_request", "provider_id")
    op.drop_index("ix_supervisor_shift_provider_id", table_name="supervisor_shift")
    op.drop_constraint("fk_supervisor_shift_provider", "supervisor_shift", type_="foreignkey")
    op.drop_column("supervisor_shift", "provider_id")
```

- [ ] **Step 6: 校验迁移与模型一致** —— 确认迁移里的列名/索引名/约束名与 Step 3 模型 `__table_args__` 完全一致：`provider_id` 两列、`ix_supervisor_shift_provider_id`、`ix_supervisor_shift_swap_request_provider_id`、`uq_supervisor_shift_property`、`uq_supervisor_shift_provider`，且 `drop_constraint("uq_supervisor_shift_tenant_date_slot", ...)` 对应旧模型里的约束名。再确认 `app/alembic/env.py` 能 import `app.models`（迁移文件无语法错）：

Run: `cd poc/backend && python3.12 -c "import importlib.util, pathlib; p = pathlib.Path('alembic/versions/24019_v220_supervisor_shift_provider_scope.py'); s = importlib.util.spec_from_file_location('m', p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); print('revision', m.revision, 'down', m.down_revision)"`
Expected: 打印 `revision 24019v220e down 24018v220d`，无异常。

- [ ] **Step 7: ruff + commit**

```bash
cd poc/backend && python3.12 -m ruff check app/models/supervisor_shift.py alembic/versions/24019_v220_supervisor_shift_provider_scope.py tests/api/test_supervisor_shift_model.py
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/models/supervisor_shift.py poc/backend/alembic/versions/24019_v220_supervisor_shift_provider_scope.py poc/backend/tests/api/test_supervisor_shift_model.py
git commit -m "feat(provider-supervisor): SupervisorShift 两表加 provider_id + partial unique index（Phase 2）"
```

---

## Task 2: `GET /supervisor/shifts` scope-aware（+ 局部 helper）

**Files:**
- Modify: `poc/backend/app/api/supervisor_shifts.py`（`_ensure_seed_week` ~40、`list_shifts` ~69）
- Test: `poc/backend/tests/api/test_supervisor_shifts_list_scope.py`

- [ ] **Step 1: 写失败测试** — 创建 `poc/backend/tests/api/test_supervisor_shifts_list_scope.py`。先 Read 一个 Phase 1 范例（`poc/backend/tests/api/test_supervisor_cases_scope.py`）确认 fixture 风格（怎么造 tenant / `ServiceProvider` / `UserAccount` / `UserTenantMembership` / JWT token / 带 auth header 的 client）。测试内容：

```python
"""Phase 2 — GET /supervisor/shifts scope 隔离测试。"""
from __future__ import annotations

# —— 按 test_supervisor_cases_scope.py 同款 import 与 fixture 风格自建 ——
# 需要：tenant 1；ServiceProvider A、B；3 个 supervisor 用户 + UserTenantMembership：
#   - 物业督导 sup_p（role='supervisor', provider_id=None, is_active=True）
#   - 服务商 A 督导 sup_a（role='supervisor', provider_id=A.id）
#   - 服务商 B 督导 sup_b（role='supervisor', provider_id=B.id）
# 每个督导一个 JWT（payload 含 tenant_id / user_id / role='supervisor' /
#   provider_id：物业侧不放该键或放 None，服务商侧放对应 id）。

def test_provider_a_supervisor_sees_own_empty_week(client, sup_a_headers):
    """服务商 A 督导首次访问 → 自动播种本服务商一周排班，全空。"""
    resp = client.get("/api/v1/supervisor/shifts", headers=sup_a_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["shifts"]) == 7
    for day in body["shifts"]:
        assert day["morning"] == "" and day["afternoon"] == "" and day["evening"] == ""


def test_dropdown_lists_only_same_scope_supervisors(
    client, sup_a_headers, sup_a, sup_b, sup_p
):
    """服务商 A 督导的下拉只含服务商 A 的督导，不含 B、不含物业。"""
    resp = client.get("/api/v1/supervisor/shifts", headers=sup_a_headers)
    names = resp.json()["supervisors"]
    assert sup_a.name in names
    assert sup_b.name not in names
    assert sup_p.name not in names


def test_provider_a_seed_does_not_leak_to_property_or_provider_b(
    client, sup_a_headers, sup_p_headers, sup_b_headers, db_session
):
    """服务商 A 督导播种后，物业侧 / 服务商 B 侧排班仍各自独立播种、互不可见。"""
    from app.models.supervisor_shift import SupervisorShift

    client.get("/api/v1/supervisor/shifts", headers=sup_a_headers)
    client.get("/api/v1/supervisor/shifts", headers=sup_p_headers)
    client.get("/api/v1/supervisor/shifts", headers=sup_b_headers)
    rows = db_session.execute(__import__("sqlalchemy").select(SupervisorShift)).scalars().all()
    by_scope: dict[object, int] = {}
    for r in rows:
        by_scope[r.provider_id] = by_scope.get(r.provider_id, 0) + 1
    # 三个 scope 各 7 天 × 3 slot = 21 行
    assert by_scope.get(None) == 21      # 物业
    assert by_scope.get(sup_a_headers_provider_id := rows[0].tenant_id and None) is None or True  # noqa
```

> 上面第 3 个测试的精确断言由实现者按 fixture 暴露的 provider id 写实（断言 `by_scope[A.id] == 21`、`by_scope[B.id] == 21`、`by_scope[None] == 21`）。最后一行占位的 walrus 仅示意——实现时删掉，改为直接用 fixture 的 `provider_a.id` / `provider_b.id` 断言。核心：三个 scope 各 21 行、互不串。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_supervisor_shifts_list_scope.py -q`
Expected: FAIL —— 服务商 A 督导持 `provider_id` token 命中 `require_tenant_roles` 的物业断言 → 403。

- [ ] **Step 3: 改 `supervisor_shifts.py`** —— 改 import、加 helper、改 `_ensure_seed_week` 与 `list_shifts`。

import 区：把 `from app.core.security import get_token_payload, require_tenant_roles` 改为 `from app.core.security import get_token_payload, require_roles`；新增两行：

```python
import sqlalchemy as sa

from ._supervisor_scope import SupervisorScope, supervisor_scope
```

在 `SLOTS = (...)` 常量后新增局部 helper：

```python
def _shift_scope_clause(
    scope: SupervisorScope,
    model: type[SupervisorShift] | type[SupervisorShiftSwapRequest],
) -> sa.ColumnElement[bool]:
    """SupervisorShift / SupervisorShiftSwapRequest 的 scope 过滤（自含 tenant_id）。

    物业侧 scope（provider_id=None）→ provider_id IS NULL；
    服务商侧 scope → provider_id == 本服务商。
    """
    if scope.provider_id is None:
        provider_cond = model.provider_id.is_(None)
    else:
        provider_cond = model.provider_id == scope.provider_id
    return sa.and_(model.tenant_id == scope.tenant_id, provider_cond)
```

把 `_ensure_seed_week` 整体替换为（签名从 `(db, tenant_id)` 改为 `(db, scope)`，播种带 `provider_id`）：

```python
def _ensure_seed_week(db: Session, scope: SupervisorScope) -> None:
    """若本 scope 本周未排班，给 7 天每个时段插入空记录（占位），让前端可编辑。"""
    today = date_type.today()
    end = today + timedelta(days=6)
    existing = db.execute(
        select(SupervisorShift.shift_date, SupervisorShift.slot)
        .where(_shift_scope_clause(scope, SupervisorShift))
        .where(SupervisorShift.shift_date.between(today, end))
    ).all()
    have = {(r[0], r[1]) for r in existing}
    inserts = []
    for i in range(7):
        d = today + timedelta(days=i)
        for s in SLOTS:
            if (d, s) not in have:
                inserts.append(
                    SupervisorShift(
                        tenant_id=scope.tenant_id,
                        provider_id=scope.provider_id,
                        shift_date=d,
                        slot=s,
                        supervisor_user_id=None,
                        supervisor_name="",
                    )
                )
    if inserts:
        db.add_all(inserts)
        db.commit()
```

把 `list_shifts` 整体替换为：

```python
@router.get("/shifts")
async def list_shifts(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    user_id = int(payload["user_id"])
    user = db.get(UserAccount, user_id)
    is_lead = _is_shift_lead(user)

    _ensure_seed_week(db, scope)

    today = date_type.today()
    end = today + timedelta(days=6)
    rows = (
        db.execute(
            select(SupervisorShift)
            .where(_shift_scope_clause(scope, SupervisorShift))
            .where(SupervisorShift.shift_date.between(today, end))
            .order_by(SupervisorShift.shift_date, SupervisorShift.slot)
        )
        .scalars()
        .all()
    )

    by_date: dict[str, dict[str, str]] = {}
    for r in rows:
        ds = r.shift_date.isoformat()
        by_date.setdefault(ds, {"morning": "", "afternoon": "", "evening": ""})
        by_date[ds][r.slot] = r.supervisor_name or ""

    # 本 scope 的督导列表，给前端做下拉
    from app.models.tenant import UserTenantMembership

    sup_q = (
        select(UserAccount.name)
        .join(UserTenantMembership, UserTenantMembership.user_id == UserAccount.id)
        .where(UserTenantMembership.tenant_id == scope.tenant_id)
        .where(UserTenantMembership.role == "supervisor")
        .where(UserAccount.is_active.is_(True))
        .distinct()
    )
    if scope.provider_id is None:
        sup_q = sup_q.where(UserTenantMembership.provider_id.is_(None))
    else:
        sup_q = sup_q.where(UserTenantMembership.provider_id == scope.provider_id)
    supervisors = [r[0] for r in db.execute(sup_q).all()]
    if user and user.name not in supervisors:
        supervisors.append(user.name)

    return {
        "tenant_id": scope.tenant_id,
        "is_shift_lead": is_lead,
        "current_user_name": user.name if user else "",
        "supervisors": supervisors,
        "shifts": [{"date": d, **slots} for d, slots in sorted(by_date.items())],
    }
```

> 注意：旧 `list_shifts` 里 `if False else []` 那段死代码占位（旧 107-117 行）随整体替换一并删除。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_supervisor_shifts_list_scope.py -q`
Expected: PASS。

- [ ] **Step 5: ruff + commit**

```bash
cd poc/backend && python3.12 -m ruff check app/api/supervisor_shifts.py tests/api/test_supervisor_shifts_list_scope.py
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/api/supervisor_shifts.py poc/backend/tests/api/test_supervisor_shifts_list_scope.py
git commit -m "feat(provider-supervisor): GET /supervisor/shifts scope-aware（Phase 2）"
```

---

## Task 3: `POST /supervisor/shifts` scope-aware

**Files:**
- Modify: `poc/backend/app/api/supervisor_shifts.py`（`save_shifts` ~141）
- Test: `poc/backend/tests/api/test_supervisor_shifts_save_scope.py`

- [ ] **Step 1: 写失败测试** — 创建 `poc/backend/tests/api/test_supervisor_shifts_save_scope.py`。fixture 风格同 Task 2（另需把某督导设为排班负责人：`UserAccount.preferences = {"is_shift_lead": True}`）。测试内容：

```python
"""Phase 2 — POST /supervisor/shifts scope 隔离测试。"""
from __future__ import annotations

from datetime import date, timedelta

import sqlalchemy as sa

from app.models.supervisor_shift import SupervisorShift


def test_provider_a_lead_saves_into_own_scope(client, sup_a_lead_headers, db_session, provider_a):
    """服务商 A 排班负责人保存 → 行落在 provider_id=A，不影响物业/B。"""
    today = date.today()
    resp = client.post(
        "/api/v1/supervisor/shifts",
        headers=sup_a_lead_headers,
        json={"shifts": [{"date": today.isoformat(), "morning": "服务商A督导",
                          "afternoon": "", "evening": ""}]},
    )
    assert resp.status_code == 200
    row = db_session.execute(
        sa.select(SupervisorShift)
        .where(SupervisorShift.shift_date == today)
        .where(SupervisorShift.slot == "morning")
        .where(SupervisorShift.provider_id == provider_a.id)
    ).scalar_one()
    assert row.supervisor_name == "服务商A督导"


def test_provider_a_save_does_not_touch_property_rows(
    client, sup_a_lead_headers, sup_p_lead_headers, db_session, provider_a
):
    """服务商 A 保存 morning，物业侧同槽位的行不受影响（partial unique 不冲突）。"""
    today = date.today()
    client.post("/api/v1/supervisor/shifts", headers=sup_p_lead_headers,
                json={"shifts": [{"date": today.isoformat(), "morning": "物业督导",
                                  "afternoon": "", "evening": ""}]})
    client.post("/api/v1/supervisor/shifts", headers=sup_a_lead_headers,
                json={"shifts": [{"date": today.isoformat(), "morning": "服务商A督导",
                                  "afternoon": "", "evening": ""}]})
    property_row = db_session.execute(
        sa.select(SupervisorShift)
        .where(SupervisorShift.shift_date == today)
        .where(SupervisorShift.slot == "morning")
        .where(SupervisorShift.provider_id.is_(None))
    ).scalar_one()
    assert property_row.supervisor_name == "物业督导"


def test_non_lead_supervisor_still_403(client, sup_a_headers):
    """非排班负责人保存 → 仍 403 ERR_NOT_SHIFT_LEAD（scope 改造不影响该校验）。"""
    resp = client.post(
        "/api/v1/supervisor/shifts",
        headers=sup_a_headers,
        json={"shifts": []},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_NOT_SHIFT_LEAD"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_supervisor_shifts_save_scope.py -q`
Expected: FAIL —— 服务商 A token 命中 `require_tenant_roles` → 403（`ERR_FORBIDDEN`，非 `ERR_NOT_SHIFT_LEAD`）。

- [ ] **Step 3: 改 `save_shifts`** —— 整体替换为：

```python
@router.post("/shifts")
async def save_shifts(
    body: dict,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """body = {"shifts": [{"date": "2026-05-08", "morning": "...", "afternoon": "...", "evening": "..."}]}"""
    user_id = int(payload["user_id"])
    user = db.get(UserAccount, user_id)
    if not _is_shift_lead(user):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ERR_NOT_SHIFT_LEAD",
                "message": "仅排班负责人可编辑全员排班；如需调班请走 swap-request",
            },
        )
    raw = body.get("shifts")
    if not isinstance(raw, list):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_VALIDATION", "message": "shifts 必须为数组"},
        )

    saved = 0
    for s in raw:
        d_str = s.get("date")
        if not isinstance(d_str, str):
            continue
        try:
            d = date_type.fromisoformat(d_str)
        except ValueError:
            continue
        for slot in SLOTS:
            name = s.get(slot, "") or ""
            row = db.execute(
                select(SupervisorShift)
                .where(_shift_scope_clause(scope, SupervisorShift))
                .where(SupervisorShift.shift_date == d)
                .where(SupervisorShift.slot == slot)
            ).scalar_one_or_none()
            if row is None:
                row = SupervisorShift(
                    tenant_id=scope.tenant_id,
                    provider_id=scope.provider_id,
                    shift_date=d,
                    slot=slot,
                    supervisor_name=name,
                )
                db.add(row)
            else:
                row.supervisor_name = name
            saved += 1
    db.commit()
    return {"saved": saved}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_supervisor_shifts_save_scope.py -q`
Expected: PASS。

- [ ] **Step 5: ruff + commit**

```bash
cd poc/backend && python3.12 -m ruff check app/api/supervisor_shifts.py tests/api/test_supervisor_shifts_save_scope.py
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/api/supervisor_shifts.py poc/backend/tests/api/test_supervisor_shifts_save_scope.py
git commit -m "feat(provider-supervisor): POST /supervisor/shifts scope-aware（Phase 2）"
```

---

## Task 4: swap-request + swap-requests scope-aware

**Files:**
- Modify: `poc/backend/app/api/supervisor_shifts.py`（`submit_swap_request` ~204、`list_swap_requests` ~272）
- Test: `poc/backend/tests/api/test_supervisor_shifts_swap_scope.py`

- [ ] **Step 1: 写失败测试** — 创建 `poc/backend/tests/api/test_supervisor_shifts_swap_scope.py`。fixture 风格同 Task 2/3。测试内容：

```python
"""Phase 2 — swap-request / swap-requests scope 隔离测试。"""
from __future__ import annotations

from datetime import date


def _seed_own_slot(client, lead_headers, slot_owner_name: str):
    """用排班负责人把今天 morning 排给某督导，返回该日期。"""
    today = date.today()
    client.post("/api/v1/supervisor/shifts", headers=lead_headers,
                json={"shifts": [{"date": today.isoformat(), "morning": slot_owner_name,
                                  "afternoon": "", "evening": ""}]})
    return today


def test_provider_a_swap_request_scoped(client, sup_a_lead_headers, sup_a, db_session, provider_a):
    """服务商 A 督导对自己班次发起调班 → swap request 带 provider_id=A。"""
    from app.models.supervisor_shift import SupervisorShiftSwapRequest

    today = _seed_own_slot(client, sup_a_lead_headers, sup_a.name)
    resp = client.post(
        "/api/v1/supervisor/shifts/swap-request",
        headers=sup_a_lead_headers,
        json={"date": today.isoformat(), "slot": "morning", "swap_with": "另一个督导"},
    )
    assert resp.status_code == 200
    req = db_session.get(SupervisorShiftSwapRequest, resp.json()["id"])
    assert req.provider_id == provider_a.id


def test_swap_requests_list_isolated(
    client, sup_a_lead_headers, sup_a, sup_b_lead_headers, sup_b, sup_p_headers
):
    """服务商 A 的调班申请，服务商 B 督导与物业督导都查不到。"""
    today_a = _seed_own_slot(client, sup_a_lead_headers, sup_a.name)
    client.post("/api/v1/supervisor/shifts/swap-request", headers=sup_a_lead_headers,
                json={"date": today_a.isoformat(), "slot": "morning", "swap_with": "X"})

    a_list = client.get("/api/v1/supervisor/shifts/swap-requests", headers=sup_a_lead_headers).json()
    b_list = client.get("/api/v1/supervisor/shifts/swap-requests", headers=sup_b_lead_headers).json()
    p_list = client.get("/api/v1/supervisor/shifts/swap-requests", headers=sup_p_headers).json()
    assert len(a_list) == 1
    assert b_list == []
    assert p_list == []


def test_swap_request_own_slot_check_scoped(client, sup_a_lead_headers, sup_p_lead_headers, sup_a):
    """物业侧把 morning 排给与服务商A督导同名的人，服务商A督导仍只能对“本scope自己的班次”发起。

    校验 _shift_scope_clause 让“自有班次”判断不跨 scope 命中。
    """
    today = date.today()
    # 物业侧把 morning 排给 sup_a.name（同名）
    client.post("/api/v1/supervisor/shifts", headers=sup_p_lead_headers,
                json={"shifts": [{"date": today.isoformat(), "morning": sup_a.name,
                                  "afternoon": "", "evening": ""}]})
    # 服务商A scope 下 morning 仍是空（没排给 sup_a）→ 发起调班应 403 ERR_NOT_OWN_SLOT
    resp = client.post(
        "/api/v1/supervisor/shifts/swap-request",
        headers=sup_a_lead_headers,
        json={"date": today.isoformat(), "slot": "morning", "swap_with": "X"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_NOT_OWN_SLOT"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_supervisor_shifts_swap_scope.py -q`
Expected: FAIL —— 服务商 A token 命中 `require_tenant_roles` → 403 `ERR_FORBIDDEN`。

- [ ] **Step 3: 改 `submit_swap_request` 与 `list_swap_requests`** —— 两个函数整体替换为：

```python
@router.post("/shifts/swap-request")
async def submit_swap_request(
    body: dict,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """body = {"date": "...", "slot": "...", "swap_with": "督导张敏"}"""
    user_id = int(payload["user_id"])
    user = db.get(UserAccount, user_id)
    d_str = body.get("date")
    slot = body.get("slot")
    swap_with = body.get("swap_with")
    if slot not in SLOTS or not isinstance(d_str, str) or not isinstance(swap_with, str):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_VALIDATION", "message": "date / slot / swap_with 必填"},
        )
    try:
        d = date_type.fromisoformat(d_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_VALIDATION", "message": "date 格式无效"},
        ) from exc

    row = db.execute(
        select(SupervisorShift)
        .where(_shift_scope_clause(scope, SupervisorShift))
        .where(SupervisorShift.shift_date == d)
        .where(SupervisorShift.slot == slot)
    ).scalar_one_or_none()
    if not user or not row or row.supervisor_name != user.name:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NOT_OWN_SLOT", "message": "只能对自己已排的班次发起调班"},
        )

    req = SupervisorShiftSwapRequest(
        tenant_id=scope.tenant_id,
        provider_id=scope.provider_id,
        from_user_id=user_id,
        from_user_name=user.name,
        to_user_name=swap_with,
        shift_date=d,
        slot=slot,
        status="pending_confirm",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {
        "id": req.id,
        "tenant_id": req.tenant_id,
        "from_user": req.from_user_name,
        "to_user": req.to_user_name,
        "date": req.shift_date.isoformat(),
        "slot": req.slot,
        "status": req.status,
        "created_at": req.created_at.isoformat() if req.created_at else None,
    }


@router.get("/shifts/swap-requests")
async def list_swap_requests(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    scope: Annotated[SupervisorScope, Depends(supervisor_scope)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    rows = (
        db.execute(
            select(SupervisorShiftSwapRequest)
            .where(_shift_scope_clause(scope, SupervisorShiftSwapRequest))
            .order_by(SupervisorShiftSwapRequest.id.desc())
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "from_user": r.from_user_name,
            "to_user": r.to_user_name,
            "date": r.shift_date.isoformat(),
            "slot": r.slot,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
```

> `payload` 参数在 `submit_swap_request` 仍用于 `user_id`，保留；`list_swap_requests` 不再用 `payload`（旧版用它取 tenant_id），但 `require_roles` / `supervisor_scope` 需要 token —— `supervisor_scope` 自身依赖 `get_token_payload`，故 `list_swap_requests` 可**删掉 `payload` 参数**。删除后确认 `get_token_payload` 仍被本文件其它端点引用（`list_shifts` / `save_shifts` / `submit_swap_request` 都用），import 保留。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_supervisor_shifts_swap_scope.py -q`
Expected: PASS。

- [ ] **Step 5: ruff + commit**

```bash
cd poc/backend && python3.12 -m ruff check app/api/supervisor_shifts.py tests/api/test_supervisor_shifts_swap_scope.py
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/api/supervisor_shifts.py poc/backend/tests/api/test_supervisor_shifts_swap_scope.py
git commit -m "feat(provider-supervisor): swap-request/swap-requests scope-aware（Phase 2）"
```

---

## Task 5: 前端 nav 补「值班排班」

**Files:**
- Modify: `frontend/src/config/nav.ts`（`SUPERVISOR_PROVIDER_NAV`）
- Modify: `frontend/src/config/__tests__/nav.test.ts`

- [ ] **Step 1: 写失败测试** — 在 `frontend/src/config/__tests__/nav.test.ts` 的「provider supervisor nav (Phase 1)」测试组里，给 provider 督导那条测试补断言（先 Read 该文件定位 `getNavSections("supervisor", "provider:2")` 的用例）：

```ts
it("provider supervisor nav 含值班排班（Phase 2）", () => {
  const paths = getNavSections("supervisor", "provider:2")
    .flatMap((s) => s.items)
    .map((i) => i.path);
  expect(paths).toContain("/supervisor/shifts");
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/config/__tests__/nav.test.ts`
Expected: FAIL —— 新用例 `expect(paths).toContain("/supervisor/shifts")` 失败。

> 注意：Phase 1 的测试里若有 `expect(paths).not.toContain("/supervisor/shifts")` 的旧断言（Phase 1 计划明确把排班排除在外），本步骤须把那条旧断言删除/改写 —— 它与 Phase 2 行为冲突。先 Read 确认。

- [ ] **Step 3: 改 `nav.ts`** —— `SUPERVISOR_PROVIDER_NAV` 的「我的工作」区，在「团队报表」项后加一项「值班排班」。该区当前是：

```ts
    {
      title: "我的工作",
      items: [
        { label: "我的 KPI", path: "/supervisor/my-kpi", icon: "BarChart3" },
        { label: "团队报表", path: "/supervisor/stats", icon: "BarChart2" },
      ],
    },
```

改为（label/icon 复用 `NAV_CONFIG.supervisor` 里 `/supervisor/shifts` 那项的既有值——「值班排班」/ `Calendar`）：

```ts
    {
      title: "我的工作",
      items: [
        { label: "我的 KPI", path: "/supervisor/my-kpi", icon: "BarChart3" },
        { label: "值班排班", path: "/supervisor/shifts", icon: "Calendar" },
        { label: "团队报表", path: "/supervisor/stats", icon: "BarChart2" },
      ],
    },
```

- [ ] **Step 4: 跑测试确认通过 + typecheck**

Run: `cd frontend && npx vitest run src/config/__tests__/nav.test.ts && npx tsc -p tsconfig.json --noEmit`
Expected: 测试 PASS；tsc 退出码 0、无输出。

- [ ] **Step 5: lint + commit**

```bash
cd frontend && npx eslint src/config/nav.ts src/config/__tests__/nav.test.ts
cd /Users/shuo/AI/autoluyin
git add frontend/src/config/nav.ts frontend/src/config/__tests__/nav.test.ts
git commit -m "feat(provider-supervisor): SUPERVISOR_PROVIDER_NAV 补值班排班（Phase 2）"
```

---

## Task 6: 全量回归 + 标注 spec

**Files:**
- Modify: `docs/superpowers/specs/2026-05-18-provider-supervisor-phase2-shifts-design.md`
- Modify: `docs/superpowers/specs/2026-05-17-provider-supervisor-workspace-design.md`

- [ ] **Step 1: 后端全量回归**

Run: `cd poc/backend && python3.12 -m pytest -q`
Expected: 全绿（既有 850 passed + 本计划新增 ~16 个测试）。若有失败，先修再继续。

- [ ] **Step 2: 前端回归 + typecheck**

Run: `cd frontend && npx vitest run && npx tsc -p tsconfig.json --noEmit`
Expected: vitest 全绿；tsc 退出码 0。

- [ ] **Step 3: 标注 Phase 2 spec** —— 在 `docs/superpowers/specs/2026-05-18-provider-supervisor-phase2-shifts-design.md` 末尾「风险」节后追加：

```markdown

---

> ✅ **Phase 2 已实现（2026-05-18）**：`SupervisorShift` / `SupervisorShiftSwapRequest` 两表加 `provider_id` + partial unique index；4 个 `/supervisor/shifts` 端点 scope-aware；前端 nav 补值班排班。每端点配多租户隔离测试。
```

- [ ] **Step 4: 更新 Phase 1 spec 的 Phase 2 状态** —— 在 `docs/superpowers/specs/2026-05-17-provider-supervisor-workspace-design.md` 末尾，把那行 `⬜ Phase 2（值班排班）待启动` 改为：

```markdown
> ✅ **Phase 2（值班排班）已实现（2026-05-18）** —— 见 `2026-05-18-provider-supervisor-phase2-shifts-design.md`。
```

- [ ] **Step 5: commit**

```bash
cd /Users/shuo/AI/autoluyin
git add docs/superpowers/specs/2026-05-18-provider-supervisor-phase2-shifts-design.md docs/superpowers/specs/2026-05-17-provider-supervisor-workspace-design.md
git commit -m "docs(provider-supervisor): Phase 2 标注实现完成"
```

---

## Self-Review

**1. Spec 覆盖**：
- 设计文档「① 数据模型迁移」→ Task 1（两表加 `provider_id` + partial unique index + Alembic 迁移）。✓
- 「② 4 个端点 scope 改造」→ Task 2（`GET /shifts` + `_ensure_seed_week` + 下拉 + helper）、Task 3（`POST /shifts`）、Task 4（swap 两端点）。✓
- 「③ 前端」→ Task 5（nav）。✓
- 「测试」多租户隔离 → Task 1（partial unique 并存）、Task 2/3/4（端点三向隔离）、Task 5（nav）。✓
- 「错误处理」沿用扁平 `{code,message}` + `ERR_NO_SCOPE` → 由 `supervisor_scope` 依赖天然提供，Task 3/4 测试还显式覆盖了 `ERR_NOT_SHIFT_LEAD`/`ERR_NOT_OWN_SLOT` 未被破坏。✓
- 「明确不在范围」accept/reject 端点、`supervisor_user_id`、排班页 UI —— 计划均未触碰。✓

**2. 占位符扫描**：Task 2 Step 1 的测试第 3 个用例末尾有一行 walrus 占位，已在该步骤正文明确标注「实现时删掉、改为用 fixture 的 `provider_a.id`/`provider_b.id` 直接断言」，并说明核心断言（三 scope 各 21 行）——这是对 fixture 具体变量名的必要留白，非逻辑占位。其余步骤均为完整代码 + 确切命令。

**3. 类型/命名一致性**：`_shift_scope_clause(scope, model)` 在 Task 2 定义、Task 3/4 引用，签名一致；`SupervisorScope` / `supervisor_scope` 来自 Phase 1 `_supervisor_scope.py`；迁移 revision `24019v220e` ← `24018v220d`；索引名 `uq_supervisor_shift_property` / `uq_supervisor_shift_provider` / `ix_supervisor_shift_provider_id` 在模型 `__table_args__`（Task 1 Step 3）与迁移（Task 1 Step 5）两处完全一致；`provider_id` FK 目标 `service_provider.id` 一致。
