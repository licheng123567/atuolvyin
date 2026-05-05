# Sprint 5b 实施计划 — 话术库管理 + LLM 调优体系

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立话术库（CRUD + 版本回滚 + Excel 导入），运行时注入 LLM prompt，督导可标注好/差话术，夜间评分 D 级自动禁用。

**Architecture:** 后端新增 3 张表（`script_template` / `script_template_version` / `tenant_suggestion_config`），扩展 `suggestion_feedback` 5 列。`RealtimeSuggestionEngine` 启动时按租户加载启用话术作为 few-shot 示例注入 system prompt。Celery cron 每天 02:00 计算采用率/转化率并打分（A/B/C/D），D 级满 20 次后自动禁用。前端新增管理员 3 页 + 督导 1 页。

**Tech Stack:** FastAPI / SQLAlchemy 2.0 / Alembic / Pydantic v2 / Celery / openpyxl / Refine.dev / shadcn/ui / Vitest / pytest + testcontainers-postgres

**Spec：** `docs/superpowers/specs/2026-05-05-sprint-5b-script-library-design.md`

---

## File Map（38 个文件）

### 后端（22 个）

| 路径 | 操作 | 责任 |
|------|------|------|
| `poc/backend/requirements.txt` | 修改 | 新增 `openpyxl==3.1.5` |
| `poc/backend/alembic/versions/5b_001_script_library.py` | 新建 | 3 张新表 + suggestion_feedback 加 5 列 |
| `poc/backend/app/models/script.py` | 新建 | `ScriptTemplate` / `ScriptTemplateVersion` / `TenantSuggestionConfig` |
| `poc/backend/app/models/__init__.py` | 修改 | 导出新 ORM |
| `poc/backend/app/models/call.py` | 修改 | `SuggestionFeedback` 加 5 列 |
| `poc/backend/app/schemas/script.py` | 新建 | 所有话术库 Pydantic schema |
| `poc/backend/app/schemas/call.py` | 修改 | `SuggestionFeedbackIn` 加 `script_template_id` |
| `poc/backend/app/services/signal_inference.py` | 新建 | `infer_signals_for_call()` 同步函数 |
| `poc/backend/app/services/realtime_llm.py` | 修改 | 注入话术 + 灵敏度 + max_per_push |
| `poc/backend/app/api/admin_scripts.py` | 新建 | CRUD + 版本 + 回滚 + 导入 |
| `poc/backend/app/api/supervisor_labels.py` | 新建 | 督导标注 API |
| `poc/backend/app/api/admin_suggestion_config.py` | 新建 | 推送配置读写 |
| `poc/backend/app/api/calls_v1.py` | 修改 | tag 写入后调 `infer_signals_for_call`；feedback 写入处理 `script_template_id` 与 `usage_count` |
| `poc/backend/app/ws/call_session.py` | 修改 | `start()` 加载脚本 + config 注入 engine |
| `poc/backend/app/main.py` | 修改 | 注册 3 个新 router |
| `poc/backend/app/worker/tasks/script_grading.py` | 新建 | Celery 夜间评分任务 |
| `poc/backend/tests/api/test_admin_scripts.py` | 新建 | CRUD + 版本 + 角色权限 |
| `poc/backend/tests/api/test_script_import.py` | 新建 | Excel 导入 |
| `poc/backend/tests/api/test_supervisor_labels.py` | 新建 | 标注 + bad 必填校验 |
| `poc/backend/tests/api/test_suggestion_config.py` | 新建 | 配置读写 |
| `poc/backend/tests/services/test_prompt_injection.py` | 新建 | few-shot 注入 |
| `poc/backend/tests/services/test_signal_inference.py` | 新建 | 信号推断纯函数 |
| `poc/backend/tests/worker/test_script_grading.py` | 新建 | 评分 + D 级自动禁用 |

### PC 前端（10 个）

| 路径 | 操作 |
|------|------|
| `frontend/src/pages/admin/scripts/list.tsx` | 新建 |
| `frontend/src/pages/admin/scripts/ScriptSheet.tsx` | 新建（新增/编辑抽屉） |
| `frontend/src/pages/admin/scripts/versions.tsx` | 新建 |
| `frontend/src/pages/admin/scripts/ImportModal.tsx` | 新建 |
| `frontend/src/pages/admin/scripts/helpers.ts` | 新建（`getScoreGradeColor` 等纯函数） |
| `frontend/src/pages/supervisor/script-labels.tsx` | 新建 |
| `frontend/src/pages/supervisor/helpers.ts` | 新建 |
| `frontend/src/App.tsx` | 修改（注册新路由 + 资源） |
| `frontend/src/pages/admin/scripts/__tests__/helpers.test.ts` | 新建 |
| `frontend/src/pages/supervisor/__tests__/helpers.test.ts` | 新建 |

---

## Read Before Starting

实现前必读：
1. `docs/superpowers/specs/2026-05-05-sprint-5b-script-library-design.md` — 完整需求
2. `poc/backend/tests/conftest.py` — fixture 列表（`seeded_tenant` / `admin_auth_headers` / `agent_auth_headers` / `supervisor_auth_headers`）
3. `poc/backend/app/models/call.py` — `SuggestionFeedback` 现有定义
4. `poc/backend/app/services/realtime_llm.py` — `RealtimeSuggestionEngine` + `Suggestion` 现有定义
5. `poc/backend/app/ws/call_session.py` — `CallSession.start()` 创建 engine 的位置
6. `poc/backend/app/api/calls_v1.py:425-560` — `patch_call_tag` 与 `post_suggestion_feedback`
7. `poc/backend/app/worker/tasks/call_pipeline.py` — Celery task + sync session 模式
8. `poc/backend/alembic/versions/4001a1b2c3d4_4_001_realtime_websocket.py` — 上一个 migration（新 migration 的 down_revision）
9. `frontend/src/pages/admin/cases/index.tsx` — 列表页 Refine + shadcn/ui 模板

---


---

## Task 1: ORM 模型（script.py 新文件 + call.py 扩展）

**Files:**
- Create: `poc/backend/app/models/script.py`
- Modify: `poc/backend/app/models/call.py`（SuggestionFeedback 加 5 列）
- Modify: `poc/backend/app/models/__init__.py`

- [ ] **Step 1: 写失败测试**

```python
# poc/backend/tests/test_models.py — 追加到文件末尾
def test_script_template_model_exists(db_session):
    from app.models.script import ScriptTemplate, ScriptTemplateVersion, TenantSuggestionConfig
    s = ScriptTemplate(
        title="测试话术",
        trigger_intent="经济困难",
        content="您好，了解到您目前有资金压力，可以考虑分期缴纳。",
        version=1,
        is_active=True,
        usage_count=0,
    )
    db_session.add(s)
    db_session.flush()
    assert s.id is not None

    v = ScriptTemplateVersion(
        script_template_id=s.id,
        version=1,
        title=s.title,
        trigger_intent=s.trigger_intent,
        content=s.content,
    )
    db_session.add(v)
    db_session.flush()
    assert v.id is not None

    cfg = TenantSuggestionConfig(tenant_id=1, sensitivity=3, max_per_push=3)
    db_session.add(cfg)
    db_session.flush()
    assert cfg.id is not None
```

- [ ] **Step 2: 运行，期望 FAIL**

```bash
cd poc/backend && pytest tests/test_models.py::test_script_template_model_exists -v
# Expected: FAIL — ImportError: cannot import name 'ScriptTemplate'
```

- [ ] **Step 3: 实现 `app/models/script.py`**

```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ScriptTemplate(Base):
    __tablename__ = "script_template"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    trigger_intent: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    usage_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    adoption_rate: Mapped[Optional[float]] = mapped_column(sa.Float)
    conversion_rate: Mapped[Optional[float]] = mapped_column(sa.Float)
    score_grade: Mapped[Optional[str]] = mapped_column(sa.String(1))
    created_by: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("user_account.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(),
        onupdate=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.Index("idx_script_template_tenant", "tenant_id"),
        sa.Index("idx_script_template_active", "tenant_id", "is_active"),
    )


class ScriptTemplateVersion(Base):
    __tablename__ = "script_template_version"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    script_template_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("script_template.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    title: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    trigger_intent: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)
    edited_by: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("user_account.id"), nullable=True
    )
    edited_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        sa.UniqueConstraint("script_template_id", "version", name="uq_script_version"),
    )


class TenantSuggestionConfig(Base):
    __tablename__ = "tenant_suggestion_config"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    sensitivity: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, default=3)
    max_per_push: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, default=3)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(),
        onupdate=sa.func.now(), nullable=False
    )
```

- [ ] **Step 4: 修改 `app/models/call.py` — 为 SuggestionFeedback 加 5 列**

在 `SuggestionFeedback` 类的 `created_at` 之后追加：

```python
    supervisor_label: Mapped[Optional[str]] = mapped_column(sa.String(16))  # good | bad
    supervisor_note: Mapped[Optional[str]] = mapped_column(sa.Text)
    supervisor_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("user_account.id"), nullable=True
    )
    supervisor_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    inferred_signal: Mapped[Optional[int]] = mapped_column(sa.SmallInteger)
    script_template_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, sa.ForeignKey("script_template.id"), nullable=True
    )
```

- [ ] **Step 5: 修改 `app/models/__init__.py`**

在 `from .call import ...` 行中追加 `SuggestionFeedback`（若还没导出），并加：

```python
from .script import ScriptTemplate, ScriptTemplateVersion, TenantSuggestionConfig
```

`__all__` 列表同步添加这三个名称。

- [ ] **Step 6: 运行测试，期望 PASS**

```bash
cd poc/backend && pytest tests/test_models.py::test_script_template_model_exists -v
# Expected: PASS
```

- [ ] **Step 7: 跑全量测试确认无回归**

```bash
cd poc/backend && pytest tests/ -v -x
# Expected: all PASS
```

- [ ] **Step 8: Commit**

```bash
git add poc/backend/app/models/script.py poc/backend/app/models/call.py poc/backend/app/models/__init__.py poc/backend/tests/test_models.py
git commit -m "feat(5b-T1): add ScriptTemplate/Version/Config ORM + extend SuggestionFeedback"
```

---

## Task 2: Alembic Migration 5b_001

**Files:**
- Create: `poc/backend/alembic/versions/5b001_script_library.py`

- [ ] **Step 1: 创建 migration 文件**

```python
# poc/backend/alembic/versions/5b001_script_library.py
"""5b-001 — script library tables + suggestion_feedback extensions.

Revision ID: 5b001
Revises: 4001a1b2c3d4
Create Date: 2026-05-05 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "5b001"
down_revision = "4001a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "script_template",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("trigger_intent", sa.String(64), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("usage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("adoption_rate", sa.Float),
        sa.Column("conversion_rate", sa.Float),
        sa.Column("score_grade", sa.String(1)),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("user_account.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_script_template_tenant", "script_template", ["tenant_id"])
    op.create_index("idx_script_template_active", "script_template", ["tenant_id", "is_active"])

    op.create_table(
        "script_template_version",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("script_template_id", sa.Integer,
                  sa.ForeignKey("script_template.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("trigger_intent", sa.String(64), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("edited_by", sa.Integer, sa.ForeignKey("user_account.id"), nullable=True),
        sa.Column("edited_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("script_template_id", "version", name="uq_script_version"),
    )

    op.create_table(
        "tenant_suggestion_config",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer,
                  sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("sensitivity", sa.SmallInteger, nullable=False, server_default="3"),
        sa.Column("max_per_push", sa.SmallInteger, nullable=False, server_default="3"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.add_column("suggestion_feedback",
        sa.Column("supervisor_label", sa.String(16)))
    op.add_column("suggestion_feedback",
        sa.Column("supervisor_note", sa.Text))
    op.add_column("suggestion_feedback",
        sa.Column("supervisor_id", sa.Integer,
                  sa.ForeignKey("user_account.id"), nullable=True))
    op.add_column("suggestion_feedback",
        sa.Column("supervisor_at", sa.DateTime(timezone=True)))
    op.add_column("suggestion_feedback",
        sa.Column("inferred_signal", sa.SmallInteger))
    op.add_column("suggestion_feedback",
        sa.Column("script_template_id", sa.Integer,
                  sa.ForeignKey("script_template.id"), nullable=True))


def downgrade() -> None:
    for col in ("script_template_id", "inferred_signal", "supervisor_at",
                "supervisor_id", "supervisor_note", "supervisor_label"):
        op.drop_column("suggestion_feedback", col)
    op.drop_table("tenant_suggestion_config")
    op.drop_table("script_template_version")
    op.drop_index("idx_script_template_active", "script_template")
    op.drop_index("idx_script_template_tenant", "script_template")
    op.drop_table("script_template")
```

- [ ] **Step 2: 验证 migration 可运行（使用测试 DB）**

migration 本身由 testcontainers 在 `Base.metadata.create_all` 时自动建表，但仍需确认文件语法无误：

```bash
cd poc/backend && python -c "import alembic.versions.5b001_script_library as m; print('OK')" 2>&1 || python -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('m', 'alembic/versions/5b001_script_library.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print('migration syntax OK')
"
```

- [ ] **Step 3: 运行全量测试（ORM 建表走 create_all，migration 无需手跑）**

```bash
cd poc/backend && pytest tests/ -v -x
# Expected: all PASS — testcontainers via create_all creates all tables
```

- [ ] **Step 4: Commit**

```bash
git add poc/backend/alembic/versions/5b001_script_library.py
git commit -m "feat(5b-T2): Alembic migration 5b_001 — script library tables"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `poc/backend/app/schemas/script.py`
- Modify: `poc/backend/app/schemas/call.py`（SuggestionFeedbackIn 加 script_template_id）

- [ ] **Step 1: 写失败测试**

```python
# poc/backend/tests/test_schemas.py — 追加
def test_script_schemas_import_and_validate():
    from app.schemas.script import (
        ScriptTemplateCreate, ScriptTemplateUpdate, ScriptTemplateOut,
        ScriptVersionOut, ImportResultOut,
        SupervisorLabelCreate, SuggestionConfigOut, SuggestionConfigUpdate,
    )
    obj = ScriptTemplateCreate(title="T", trigger_intent="其他", content="内容")
    assert obj.title == "T"

    label = SupervisorLabelCreate(label="bad", note="有问题")
    assert label.label == "bad"

    # bad 话术必须有 note
    from pydantic import ValidationError
    import pytest
    with pytest.raises(ValidationError):
        SupervisorLabelCreate(label="bad")

def test_suggestion_feedbackin_accepts_script_template_id():
    from app.schemas.call import SuggestionFeedbackIn
    fb = SuggestionFeedbackIn(action="adopt", script_template_id=5)
    assert fb.script_template_id == 5
    fb2 = SuggestionFeedbackIn(action="ignore")
    assert fb2.script_template_id is None
```

- [ ] **Step 2: 运行，期望 FAIL**

```bash
cd poc/backend && pytest tests/test_schemas.py::test_script_schemas_import_and_validate tests/test_schemas.py::test_suggestion_feedbackin_accepts_script_template_id -v
# Expected: FAIL
```

- [ ] **Step 3: 实现 `app/schemas/script.py`**

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScriptTemplateCreate(BaseModel):
    title: str = Field(..., max_length=128)
    trigger_intent: str = Field(..., max_length=64)
    content: str
    notes: Optional[str] = None


class ScriptTemplateUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=128)
    trigger_intent: Optional[str] = Field(None, max_length=64)
    content: Optional[str] = None
    notes: Optional[str] = None


class ScriptTemplateOut(BaseModel):
    id: int
    tenant_id: Optional[int]
    title: str
    trigger_intent: str
    content: str
    notes: Optional[str]
    version: int
    is_active: bool
    usage_count: int
    adoption_rate: Optional[float]
    conversion_rate: Optional[float]
    score_grade: Optional[str]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ScriptVersionOut(BaseModel):
    version: int
    title: str
    trigger_intent: str
    content: str
    notes: Optional[str]
    edited_by: Optional[int]
    edited_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RollbackIn(BaseModel):
    to_version: int


class ImportResultOut(BaseModel):
    success: int
    skipped: int
    failed: int
    errors: list[str]


class SupervisorLabelCreate(BaseModel):
    label: Literal["good", "bad"]
    note: Optional[str] = None

    @model_validator(mode="after")
    def note_required_for_bad(self) -> "SupervisorLabelCreate":
        if self.label == "bad" and not self.note:
            raise ValueError("差话术标注必须填写点评")
        return self


class SupervisorLabelOut(BaseModel):
    feedback_id: int
    call_id: int
    suggestion_text: str
    supervisor_label: Optional[str]
    supervisor_note: Optional[str]
    script_template_id: Optional[int]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SuggestionConfigOut(BaseModel):
    sensitivity: int
    max_per_push: int


class SuggestionConfigUpdate(BaseModel):
    sensitivity: int = Field(..., ge=1, le=5)
    max_per_push: int = Field(..., ge=1, le=10)
```

- [ ] **Step 4: 修改 `app/schemas/call.py` — SuggestionFeedbackIn 加字段**

找到：
```python
class SuggestionFeedbackIn(BaseModel):
    action: str  # "adopt" | "ignore"
    suggestion_text: Optional[str] = None
```

替换为：
```python
class SuggestionFeedbackIn(BaseModel):
    action: str  # "adopt" | "ignore"
    suggestion_text: Optional[str] = None
    script_template_id: Optional[int] = None
```

- [ ] **Step 5: 运行测试，期望 PASS**

```bash
cd poc/backend && pytest tests/test_schemas.py::test_script_schemas_import_and_validate tests/test_schemas.py::test_suggestion_feedbackin_accepts_script_template_id -v
```

- [ ] **Step 6: Commit**

```bash
git add poc/backend/app/schemas/script.py poc/backend/app/schemas/call.py poc/backend/tests/test_schemas.py
git commit -m "feat(5b-T3): add script library Pydantic schemas + extend SuggestionFeedbackIn"
```

---

## Task 4: 业务信号推断服务

**Files:**
- Create: `poc/backend/app/services/signal_inference.py`
- Create: `poc/backend/tests/services/test_signal_inference.py`

- [ ] **Step 1: 写失败测试**

```python
# poc/backend/tests/services/test_signal_inference.py
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import select


def test_infer_signal_payment_confirmed_returns_plus1(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from datetime import datetime, timezone
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord, SuggestionFeedback
    from app.models.script import ScriptTemplate
    from app.services.signal_inference import infer_signals_for_call

    # 建立 script_template
    script = ScriptTemplate(
        title="催费话术",
        trigger_intent="经济困难",
        content="建议分期缴纳",
        version=1,
    )
    db_session.add(script)
    db_session.flush()

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000001"),
        initiated_by="app",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration_sec=60,
        status="processed",
    )
    db_session.add(call)
    db_session.flush()

    fb = SuggestionFeedback(
        call_id=call.id,
        suggestion_id="sug-001",
        user_id=seeded_member_user.id,
        action="adopt",
        suggestion_text="建议分期",
        script_template_id=script.id,
    )
    db_session.add(fb)
    db_session.flush()

    infer_signals_for_call(call.id, "payment_confirmed", db_session)
    db_session.expire(fb)
    assert fb.inferred_signal == 1


def test_infer_signal_complaint_returns_minus1(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from datetime import datetime, timezone
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord, SuggestionFeedback
    from app.models.script import ScriptTemplate
    from app.services.signal_inference import infer_signals_for_call

    script = ScriptTemplate(title="t", trigger_intent="其他", content="c", version=1)
    db_session.add(script)
    db_session.flush()

    call = CallRecord(
        tenant_id=seeded_tenant.id, case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000002"),
        initiated_by="app", status="processed",
    )
    db_session.add(call)
    db_session.flush()

    fb = SuggestionFeedback(
        call_id=call.id, suggestion_id="sug-002",
        user_id=seeded_member_user.id, action="ignore",
        suggestion_text="t", script_template_id=script.id,
    )
    db_session.add(fb)
    db_session.flush()

    infer_signals_for_call(call.id, "complaint", db_session)
    db_session.expire(fb)
    assert fb.inferred_signal == -1


def test_infer_signal_unknown_intent_returns_zero(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from datetime import datetime, timezone
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord, SuggestionFeedback
    from app.models.script import ScriptTemplate
    from app.services.signal_inference import infer_signals_for_call

    script = ScriptTemplate(title="t", trigger_intent="其他", content="c", version=1)
    db_session.add(script)
    db_session.flush()

    call = CallRecord(
        tenant_id=seeded_tenant.id, case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000003"),
        initiated_by="app", status="processed",
    )
    db_session.add(call)
    db_session.flush()

    fb = SuggestionFeedback(
        call_id=call.id, suggestion_id="sug-003",
        user_id=seeded_member_user.id, action="adopt",
        suggestion_text="t", script_template_id=script.id,
    )
    db_session.add(fb)
    db_session.flush()

    infer_signals_for_call(call.id, "no_answer", db_session)
    db_session.expire(fb)
    assert fb.inferred_signal == 0
```

- [ ] **Step 2: 运行，期望 FAIL**

```bash
cd poc/backend && pytest tests/services/test_signal_inference.py -v
# Expected: FAIL — ImportError
```

- [ ] **Step 3: 实现 `app/services/signal_inference.py`**

```python
from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.call import SuggestionFeedback


def infer_signals_for_call(call_id: int, intent: str, db: Session) -> None:
    if intent in ("payment_confirmed", "promise_made"):
        signal = 1
    elif intent in ("complaint",):
        signal = -1
    else:
        signal = 0

    db.execute(
        update(SuggestionFeedback)
        .where(
            SuggestionFeedback.call_id == call_id,
            SuggestionFeedback.script_template_id.is_not(None),
        )
        .values(inferred_signal=signal)
    )
    db.flush()
```

- [ ] **Step 4: 运行测试，期望 PASS**

```bash
cd poc/backend && pytest tests/services/test_signal_inference.py -v
```

- [ ] **Step 5: Commit**

```bash
git add poc/backend/app/services/signal_inference.py poc/backend/tests/services/test_signal_inference.py
git commit -m "feat(5b-T4): add signal_inference service"
```


---

## Task 5: Admin Scripts CRUD API（list / create / patch / toggle / delete / versions / rollback）

**Files:**
- Create: `poc/backend/app/api/admin_scripts.py`
- Create: `poc/backend/tests/api/test_admin_scripts.py`

- [ ] **Step 1: 写失败测试**

```python
# poc/backend/tests/api/test_admin_scripts.py
import pytest


@pytest.fixture
def seeded_script(db_session, seeded_tenant):
    from app.models.script import ScriptTemplate, ScriptTemplateVersion
    s = ScriptTemplate(
        tenant_id=seeded_tenant.id,
        title="分期建议",
        trigger_intent="经济困难",
        content="您好，了解到您有资金压力，可以分期缴纳。",
        version=1,
    )
    db_session.add(s)
    db_session.flush()
    v = ScriptTemplateVersion(
        script_template_id=s.id, version=1,
        title=s.title, trigger_intent=s.trigger_intent, content=s.content,
    )
    db_session.add(v)
    db_session.flush()
    return s


@pytest.mark.asyncio
async def test_list_scripts_returns_items(client, admin_auth_headers, seeded_script):
    resp = await client.get("/api/v1/admin/scripts", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    ids = [i["id"] for i in body["items"]]
    assert seeded_script.id in ids


@pytest.mark.asyncio
async def test_create_script_writes_snapshot(client, admin_auth_headers, db_session, seeded_tenant):
    from app.models.script import ScriptTemplateVersion
    from sqlalchemy import select
    resp = await client.post(
        "/api/v1/admin/scripts",
        json={"title": "新话术", "trigger_intent": "服务不满", "content": "非常抱歉给您带来不便"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    script_id = resp.json()["id"]
    versions = db_session.execute(
        select(ScriptTemplateVersion).where(ScriptTemplateVersion.script_template_id == script_id)
    ).scalars().all()
    assert len(versions) == 1
    assert versions[0].version == 1


@pytest.mark.asyncio
async def test_patch_script_increments_version(client, admin_auth_headers, seeded_script, db_session):
    from app.models.script import ScriptTemplateVersion
    from sqlalchemy import select
    resp = await client.patch(
        f"/api/v1/admin/scripts/{seeded_script.id}",
        json={"content": "更新后的话术内容"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["version"] == 2
    versions = db_session.execute(
        select(ScriptTemplateVersion).where(ScriptTemplateVersion.script_template_id == seeded_script.id)
    ).scalars().all()
    assert len(versions) == 2


@pytest.mark.asyncio
async def test_toggle_script(client, admin_auth_headers, seeded_script):
    resp = await client.post(f"/api/v1/admin/scripts/{seeded_script.id}/toggle", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    # toggle back
    resp2 = await client.post(f"/api/v1/admin/scripts/{seeded_script.id}/toggle", headers=admin_auth_headers)
    assert resp2.json()["is_active"] is True


@pytest.mark.asyncio
async def test_delete_requires_inactive(client, admin_auth_headers, seeded_script):
    resp = await client.delete(f"/api/v1/admin/scripts/{seeded_script.id}", headers=admin_auth_headers)
    assert resp.status_code == 400  # still active

    await client.post(f"/api/v1/admin/scripts/{seeded_script.id}/toggle", headers=admin_auth_headers)
    resp2 = await client.delete(f"/api/v1/admin/scripts/{seeded_script.id}", headers=admin_auth_headers)
    assert resp2.status_code == 204


@pytest.mark.asyncio
async def test_versions_list(client, admin_auth_headers, seeded_script, client, admin_auth_headers):
    resp = await client.get(f"/api/v1/admin/scripts/{seeded_script.id}/versions", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_rollback(client, admin_auth_headers, seeded_script, db_session):
    from app.models.script import ScriptTemplate, ScriptTemplateVersion
    from sqlalchemy import select
    # patch to v2
    await client.patch(
        f"/api/v1/admin/scripts/{seeded_script.id}",
        json={"content": "v2内容"},
        headers=admin_auth_headers,
    )
    resp = await client.post(
        f"/api/v1/admin/scripts/{seeded_script.id}/rollback",
        json={"to_version": 1},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["version"] == 3  # new snapshot = v3

    db_session.expire_all()
    s = db_session.get(ScriptTemplate, seeded_script.id)
    assert s.content == "您好，了解到您有资金压力，可以分期缴纳。"
    versions = db_session.execute(
        select(ScriptTemplateVersion).where(ScriptTemplateVersion.script_template_id == s.id)
    ).scalars().all()
    assert len(versions) == 3
```

- [ ] **Step 2: 运行，期望 FAIL**

```bash
cd poc/backend && pytest tests/api/test_admin_scripts.py -v
# Expected: FAIL — 404 (routes not registered)
```

- [ ] **Step 3: 实现 `app/api/admin_scripts.py`**

```python
# poc/backend/app/api/admin_scripts.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.script import ScriptTemplate, ScriptTemplateVersion
from app.schemas.script import (
    ImportResultOut, RollbackIn, ScriptTemplateCreate,
    ScriptTemplateOut, ScriptTemplateUpdate, ScriptVersionOut,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()

ADMIN_ROLES = ("admin", "platform_superadmin")


def _tenant_filter(payload: dict, q: "type[ScriptTemplate]") -> "object":
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    if role == "platform_superadmin":
        return q
    return q.where(or_(ScriptTemplate.tenant_id == tenant_id, ScriptTemplate.tenant_id.is_(None)))


def _write_snapshot(db: Session, script: ScriptTemplate, editor_id: int) -> None:
    v = ScriptTemplateVersion(
        script_template_id=script.id,
        version=script.version,
        title=script.title,
        trigger_intent=script.trigger_intent,
        content=script.content,
        notes=script.notes,
        edited_by=editor_id,
    )
    db.add(v)


@router.get("/scripts", response_model=PaginatedResponse[ScriptTemplateOut])
def list_scripts(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    q: Optional[str] = Query(None),
    intent: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ScriptTemplateOut]:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)

    stmt = select(ScriptTemplate)
    if role != "platform_superadmin":
        stmt = stmt.where(
            or_(ScriptTemplate.tenant_id == tenant_id, ScriptTemplate.tenant_id.is_(None))
        )
    if q:
        stmt = stmt.where(
            or_(ScriptTemplate.title.ilike(f"%{q}%"), ScriptTemplate.content.ilike(f"%{q}%"))
        )
    if intent:
        stmt = stmt.where(ScriptTemplate.trigger_intent == intent)
    if status == "active":
        stmt = stmt.where(ScriptTemplate.is_active.is_(True))
    elif status == "inactive":
        stmt = stmt.where(ScriptTemplate.is_active.is_(False))

    total = db.execute(stmt.with_only_columns(ScriptTemplate.id)).scalars().all()
    items = db.execute(
        stmt.order_by(ScriptTemplate.updated_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return PaginatedResponse(items=items, total=len(total), page=page, page_size=page_size)


@router.post("/scripts", response_model=ScriptTemplateOut, status_code=201)
def create_script(
    body: ScriptTemplateCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ScriptTemplateOut:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    user_id = int(payload.get("user_id") or 0)

    script = ScriptTemplate(
        tenant_id=None if role == "platform_superadmin" else tenant_id,
        title=body.title,
        trigger_intent=body.trigger_intent,
        content=body.content,
        notes=body.notes,
        version=1,
        created_by=user_id,
    )
    db.add(script)
    db.flush()
    _write_snapshot(db, script, user_id)
    db.commit()
    db.refresh(script)
    return script


@router.patch("/scripts/{script_id}", response_model=ScriptTemplateOut)
def update_script(
    script_id: int,
    body: ScriptTemplateUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ScriptTemplateOut:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    user_id = int(payload.get("user_id") or 0)

    script = _get_script_or_404(db, script_id, role, tenant_id)
    _write_snapshot(db, script, user_id)

    if body.title is not None:
        script.title = body.title
    if body.trigger_intent is not None:
        script.trigger_intent = body.trigger_intent
    if body.content is not None:
        script.content = body.content
    if body.notes is not None:
        script.notes = body.notes
    script.version += 1

    db.commit()
    db.refresh(script)
    return script


@router.post("/scripts/{script_id}/toggle", response_model=ScriptTemplateOut)
def toggle_script(
    script_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ScriptTemplateOut:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    script = _get_script_or_404(db, script_id, role, tenant_id)
    script.is_active = not script.is_active
    db.commit()
    db.refresh(script)
    return script


@router.delete("/scripts/{script_id}", status_code=204)
def delete_script(
    script_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    script = _get_script_or_404(db, script_id, role, tenant_id)
    if script.is_active:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_STILL_ACTIVE", "message": "请先禁用话术再删除"},
        )
    db.delete(script)
    db.commit()


@router.get("/scripts/{script_id}/versions", response_model=list[ScriptVersionOut])
def get_versions(
    script_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> list[ScriptVersionOut]:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    _get_script_or_404(db, script_id, role, tenant_id)
    versions = db.execute(
        select(ScriptTemplateVersion)
        .where(ScriptTemplateVersion.script_template_id == script_id)
        .order_by(ScriptTemplateVersion.version.desc())
    ).scalars().all()
    return list(versions)


@router.post("/scripts/{script_id}/rollback", response_model=ScriptTemplateOut)
def rollback_script(
    script_id: int,
    body: RollbackIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ScriptTemplateOut:
    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0)
    user_id = int(payload.get("user_id") or 0)

    script = _get_script_or_404(db, script_id, role, tenant_id)
    target = db.execute(
        select(ScriptTemplateVersion).where(
            ScriptTemplateVersion.script_template_id == script_id,
            ScriptTemplateVersion.version == body.to_version,
        )
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": f"版本 {body.to_version} 不存在"},
        )

    script.title = target.title
    script.trigger_intent = target.trigger_intent
    script.content = target.content
    script.notes = target.notes
    script.version += 1
    _write_snapshot(db, script, user_id)

    db.commit()
    db.refresh(script)
    return script


def _get_script_or_404(db: Session, script_id: int, role: str, tenant_id: int) -> ScriptTemplate:
    stmt = select(ScriptTemplate).where(ScriptTemplate.id == script_id)
    if role != "platform_superadmin":
        stmt = stmt.where(
            or_(ScriptTemplate.tenant_id == tenant_id, ScriptTemplate.tenant_id.is_(None))
        )
    script = db.execute(stmt).scalar_one_or_none()
    if not script:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "话术不存在"},
        )
    return script
```

- [ ] **Step 4: 运行测试，期望 PASS（路由还未注册，先确认逻辑，下一步注册）**

注意：tests/api/test_admin_scripts.py 里的路由调用需要 main.py 注册，但我们先在 T9 统一注册。现在先跑模型/schema 测试：

```bash
cd poc/backend && pytest tests/test_models.py tests/test_schemas.py -v
```

- [ ] **Step 5: Commit（API 文件先提交，T9 注册路由后才能跑 API 测试）**

```bash
git add poc/backend/app/api/admin_scripts.py poc/backend/tests/api/test_admin_scripts.py
git commit -m "feat(5b-T5): admin scripts CRUD + version snapshot + rollback"
```

---

## Task 6: Script Import（openpyxl）

**Files:**
- Modify: `poc/backend/requirements.txt`（新增 openpyxl）
- Modify: `poc/backend/app/api/admin_scripts.py`（加 import 端点）
- Create: `poc/backend/tests/api/test_script_import.py`

- [ ] **Step 1: 写失败测试**

```python
# poc/backend/tests/api/test_script_import.py
import io
import pytest


def _make_xlsx(rows: list[tuple]) -> bytes:
    """Build minimal xlsx in memory."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["话术标题", "异议类型", "话术内容", "编写说明"])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_import_valid_rows(client, admin_auth_headers, db_session, seeded_tenant):
    from app.models.script import ScriptTemplate
    from sqlalchemy import select
    data = _make_xlsx([
        ("分期话术", "经济困难", "可以分期缴纳", "测试说明"),
        ("服务话术", "服务不满", "非常抱歉", None),
    ])
    resp = await client.post(
        "/api/v1/admin/scripts/import",
        headers=admin_auth_headers,
        files={"file": ("test.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] == 2
    assert body["skipped"] == 0
    assert body["failed"] == 0


@pytest.mark.asyncio
async def test_import_skips_duplicate_title(client, admin_auth_headers, seeded_script):
    data = _make_xlsx([("分期建议", "经济困难", "内容", None)])  # "分期建议" same as seeded_script.title
    resp = await client.post(
        "/api/v1/admin/scripts/import",
        headers=admin_auth_headers,
        files={"file": ("test.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    body = resp.json()
    assert body["skipped"] == 1
    assert body["success"] == 0


@pytest.mark.asyncio
async def test_import_fails_invalid_intent(client, admin_auth_headers):
    data = _make_xlsx([("话术X", "无效类型", "内容", None)])
    resp = await client.post(
        "/api/v1/admin/scripts/import",
        headers=admin_auth_headers,
        files={"file": ("test.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    body = resp.json()
    assert body["failed"] == 1
    assert len(body["errors"]) >= 1
```

- [ ] **Step 2: 在 requirements.txt 追加 openpyxl**

```
openpyxl==3.1.5
```

- [ ] **Step 3: 在 `app/api/admin_scripts.py` 末尾追加 import 端点**

```python
import io
from fastapi import File, UploadFile

VALID_INTENTS = {"房屋质量", "经济困难", "服务不满", "联系困难", "其他"}


@router.post("/scripts/import", response_model=ImportResultOut)
def import_scripts(
    file: Annotated[UploadFile, File(...)],
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> ImportResultOut:
    import openpyxl

    role = payload.get("role", "")
    tenant_id = int(payload.get("tenant_id") or 0) if role != "platform_superadmin" else None
    user_id = int(payload.get("user_id") or 0)

    contents = file.file.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(contents))
    except Exception:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"code": "ERR_INVALID_FILE", "message": "无法解析 Excel 文件"},
        )

    ws = wb.active
    existing_titles = {
        row[0] for row in db.execute(
            select(ScriptTemplate.title).where(
                or_(ScriptTemplate.tenant_id == tenant_id, ScriptTemplate.tenant_id.is_(None))
                if tenant_id is not None else ScriptTemplate.tenant_id.is_(None)
            )
        ).all()
    }

    success = skipped = failed = 0
    errors: list[str] = []

    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        title, intent, content, notes = (row[j] if j < len(row) else None for j in range(4))
        title = str(title).strip() if title else ""
        intent = str(intent).strip() if intent else ""
        content = str(content).strip() if content else ""
        notes = str(notes).strip() if notes else None

        if not title or not intent or not content:
            if len(errors) < 10:
                errors.append(f"第 {i} 行：标题/异议类型/内容不能为空")
            failed += 1
            continue
        if intent not in VALID_INTENTS:
            if len(errors) < 10:
                errors.append(f"第 {i} 行：异议类型「{intent}」不在枚举范围内")
            failed += 1
            continue
        if title in existing_titles:
            skipped += 1
            continue

        script = ScriptTemplate(
            tenant_id=tenant_id,
            title=title,
            trigger_intent=intent,
            content=content,
            notes=notes or None,
            version=1,
            created_by=user_id,
        )
        db.add(script)
        db.flush()
        _write_snapshot(db, script, user_id)
        existing_titles.add(title)
        success += 1

    db.commit()
    return ImportResultOut(success=success, skipped=skipped, failed=failed, errors=errors)
```

- [ ] **Step 4: 安装 openpyxl 并运行测试（需先在 T9 注册路由，这里先跑导入测试准备）**

```bash
cd poc/backend && pip install openpyxl==3.1.5
```

- [ ] **Step 5: Commit**

```bash
git add poc/backend/requirements.txt poc/backend/app/api/admin_scripts.py poc/backend/tests/api/test_script_import.py
git commit -m "feat(5b-T6): script Excel import endpoint + openpyxl"
```

---

## Task 7: Supervisor Labels API

**Files:**
- Create: `poc/backend/app/api/supervisor_labels.py`
- Create: `poc/backend/tests/api/test_supervisor_labels.py`

- [ ] **Step 1: 写失败测试**

```python
# poc/backend/tests/api/test_supervisor_labels.py
import pytest
from datetime import datetime, timezone


@pytest.fixture
def seeded_feedback_with_script(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord, SuggestionFeedback
    from app.models.script import ScriptTemplate

    script = ScriptTemplate(
        tenant_id=seeded_tenant.id,
        title="测试话术",
        trigger_intent="其他",
        content="话术内容",
        version=1,
    )
    db_session.add(script)

    call = CallRecord(
        tenant_id=seeded_tenant.id, case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000099"),
        initiated_by="app", status="processed",
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(call)
    db_session.flush()

    fb = SuggestionFeedback(
        call_id=call.id, suggestion_id="sug-sup-01",
        user_id=seeded_member_user.id, action="adopt",
        suggestion_text="话术内容", script_template_id=script.id,
    )
    db_session.add(fb)
    db_session.flush()
    return fb


@pytest.mark.asyncio
async def test_get_labels_list(client, supervisor_auth_headers, seeded_feedback_with_script):
    resp = await client.get("/api/v1/supervisor/script-labels", headers=supervisor_auth_headers)
    assert resp.status_code == 200
    ids = [item["feedback_id"] for item in resp.json()]
    assert seeded_feedback_with_script.id in ids


@pytest.mark.asyncio
async def test_post_good_label(client, supervisor_auth_headers, seeded_feedback_with_script, db_session):
    from app.models.call import SuggestionFeedback
    resp = await client.post(
        f"/api/v1/supervisor/script-labels/{seeded_feedback_with_script.id}",
        json={"label": "good"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    db_session.expire(seeded_feedback_with_script)
    assert seeded_feedback_with_script.supervisor_label == "good"


@pytest.mark.asyncio
async def test_post_bad_label_requires_note(client, supervisor_auth_headers, seeded_feedback_with_script):
    resp = await client.post(
        f"/api/v1/supervisor/script-labels/{seeded_feedback_with_script.id}",
        json={"label": "bad"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_bad_label_with_note(client, supervisor_auth_headers, seeded_feedback_with_script, db_session):
    resp = await client.post(
        f"/api/v1/supervisor/script-labels/{seeded_feedback_with_script.id}",
        json={"label": "bad", "note": "话术效果差"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 200
    db_session.expire(seeded_feedback_with_script)
    assert seeded_feedback_with_script.supervisor_label == "bad"
    assert seeded_feedback_with_script.supervisor_note == "话术效果差"
```

- [ ] **Step 2: 实现 `app/api/supervisor_labels.py`**

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.call import SuggestionFeedback
from app.schemas.script import SupervisorLabelCreate, SupervisorLabelOut

router = APIRouter()

SUPERVISOR_ROLES = ("supervisor", "admin")


@router.get("/script-labels", response_model=list[SupervisorLabelOut])
def list_script_labels(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    unread_only: bool = Query(False),
) -> list[SupervisorLabelOut]:
    tenant_id = int(payload.get("tenant_id") or 0)
    from app.models.call import CallRecord
    stmt = (
        select(SuggestionFeedback)
        .join(CallRecord, CallRecord.id == SuggestionFeedback.call_id)
        .where(
            CallRecord.tenant_id == tenant_id,
            SuggestionFeedback.script_template_id.is_not(None),
        )
        .order_by(CallRecord.started_at.desc())
        .limit(200)
    )
    if unread_only:
        stmt = stmt.where(SuggestionFeedback.supervisor_label.is_(None))
    rows = db.execute(stmt).scalars().all()
    return [
        SupervisorLabelOut(
            feedback_id=r.id,
            call_id=r.call_id,
            suggestion_text=r.suggestion_text,
            supervisor_label=r.supervisor_label,
            supervisor_note=r.supervisor_note,
            script_template_id=r.script_template_id,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/script-labels/{feedback_id}", response_model=SupervisorLabelOut)
def label_script(
    feedback_id: int,
    body: SupervisorLabelCreate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SupervisorLabelOut:
    tenant_id = int(payload.get("tenant_id") or 0)
    user_id = int(payload.get("user_id") or 0)
    from app.models.call import CallRecord
    fb = db.execute(
        select(SuggestionFeedback)
        .join(CallRecord, CallRecord.id == SuggestionFeedback.call_id)
        .where(
            SuggestionFeedback.id == feedback_id,
            CallRecord.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not fb:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "反馈记录不存在"},
        )

    fb.supervisor_label = body.label
    fb.supervisor_note = body.note
    fb.supervisor_id = user_id
    fb.supervisor_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(fb)
    return SupervisorLabelOut(
        feedback_id=fb.id, call_id=fb.call_id,
        suggestion_text=fb.suggestion_text,
        supervisor_label=fb.supervisor_label,
        supervisor_note=fb.supervisor_note,
        script_template_id=fb.script_template_id,
        created_at=fb.created_at,
    )
```

- [ ] **Step 3: Commit**

```bash
git add poc/backend/app/api/supervisor_labels.py poc/backend/tests/api/test_supervisor_labels.py
git commit -m "feat(5b-T7): supervisor script-labels API"
```

---

## Task 8: Suggestion Config API

**Files:**
- Create: `poc/backend/app/api/admin_suggestion_config.py`
- Create: `poc/backend/tests/api/test_suggestion_config.py`

- [ ] **Step 1: 写失败测试**

```python
# poc/backend/tests/api/test_suggestion_config.py
import pytest


@pytest.mark.asyncio
async def test_get_config_returns_defaults_when_no_record(client, admin_auth_headers):
    resp = await client.get("/api/v1/admin/suggestion-config", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["sensitivity"] == 3
    assert body["max_per_push"] == 3


@pytest.mark.asyncio
async def test_put_config_upserts(client, admin_auth_headers, db_session, seeded_tenant):
    from app.models.script import TenantSuggestionConfig
    from sqlalchemy import select
    resp = await client.put(
        "/api/v1/admin/suggestion-config",
        json={"sensitivity": 5, "max_per_push": 1},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["sensitivity"] == 5

    db_session.expire_all()
    cfg = db_session.execute(
        select(TenantSuggestionConfig).where(TenantSuggestionConfig.tenant_id == seeded_tenant.id)
    ).scalar_one_or_none()
    assert cfg is not None
    assert cfg.sensitivity == 5


@pytest.mark.asyncio
async def test_put_config_validates_range(client, admin_auth_headers):
    resp = await client.put(
        "/api/v1/admin/suggestion-config",
        json={"sensitivity": 6, "max_per_push": 3},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 422
```

- [ ] **Step 2: 实现 `app/api/admin_suggestion_config.py`**

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.script import TenantSuggestionConfig
from app.schemas.script import SuggestionConfigOut, SuggestionConfigUpdate

router = APIRouter()

ADMIN_ROLES = ("admin", "platform_superadmin")
_DEFAULTS = SuggestionConfigOut(sensitivity=3, max_per_push=3)


@router.get("/suggestion-config", response_model=SuggestionConfigOut)
def get_config(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SuggestionConfigOut:
    tenant_id = int(payload.get("tenant_id") or 0)
    cfg = db.execute(
        select(TenantSuggestionConfig).where(TenantSuggestionConfig.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if cfg is None:
        return _DEFAULTS
    return SuggestionConfigOut(sensitivity=cfg.sensitivity, max_per_push=cfg.max_per_push)


@router.put("/suggestion-config", response_model=SuggestionConfigOut)
def put_config(
    body: SuggestionConfigUpdate,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SuggestionConfigOut:
    tenant_id = int(payload.get("tenant_id") or 0)
    cfg = db.execute(
        select(TenantSuggestionConfig).where(TenantSuggestionConfig.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if cfg is None:
        cfg = TenantSuggestionConfig(tenant_id=tenant_id)
        db.add(cfg)

    cfg.sensitivity = body.sensitivity
    cfg.max_per_push = body.max_per_push
    cfg.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cfg)
    return SuggestionConfigOut(sensitivity=cfg.sensitivity, max_per_push=cfg.max_per_push)
```

- [ ] **Step 3: Commit**

```bash
git add poc/backend/app/api/admin_suggestion_config.py poc/backend/tests/api/test_suggestion_config.py
git commit -m "feat(5b-T8): suggestion config API with upsert"
```


---

## Task 9: main.py 注册 3 个新 Router

**Files:**
- Modify: `poc/backend/app/main.py`

- [ ] **Step 1: 修改 main.py**

找到 `app.include_router(calls_v1.router` 那一行，在 supervisor.router 那行后追加：

```python
from app.api import admin_scripts, supervisor_labels, admin_suggestion_config  # 与其他 import 一并放在顶部

# 在 include_router 区块追加：
app.include_router(admin_scripts.router, prefix="/api/v1/admin", tags=["admin-scripts"])
app.include_router(supervisor_labels.router, prefix="/api/v1/supervisor", tags=["supervisor-labels"])
app.include_router(admin_suggestion_config.router, prefix="/api/v1/admin", tags=["suggestion-config"])
```

- [ ] **Step 2: 运行全量 API 测试**

```bash
cd poc/backend && pytest tests/api/ -v -x
# Expected: all PASS（包括 test_admin_scripts, test_script_import,
#   test_supervisor_labels, test_suggestion_config）
```

- [ ] **Step 3: Commit**

```bash
git add poc/backend/app/main.py
git commit -m "feat(5b-T9): register admin-scripts, supervisor-labels, suggestion-config routers"
```

---

## Task 10: Prompt 注入（realtime_llm.py + call_session.py）

**Files:**
- Modify: `poc/backend/app/services/realtime_llm.py`
- Modify: `poc/backend/app/ws/call_session.py`
- Create: `poc/backend/tests/services/test_prompt_injection.py`

- [ ] **Step 1: 写失败测试**

```python
# poc/backend/tests/services/test_prompt_injection.py
from app.services.realtime_llm import (
    RealtimeSuggestionEngine, _build_system_prompt, _load_scripts,
)


def test_build_system_prompt_no_scripts():
    base = "你是话术助手。"
    result = _build_system_prompt({}, base)
    assert result == base


def test_build_system_prompt_with_scripts():
    scripts = {
        "经济困难": ["可以分期缴纳", "理解您的困难"],
        "服务不满": ["非常抱歉"],
    }
    base = "你是话术助手。"
    result = _build_system_prompt(scripts, base)
    assert "[参考话术 - 经济困难]" in result
    assert "可以分期缴纳" in result
    assert "[参考话术 - 服务不满]" in result


def test_load_scripts_returns_empty_when_no_active(db_session, seeded_tenant):
    result = _load_scripts(db_session, seeded_tenant.id)
    assert isinstance(result, dict)


def test_load_scripts_returns_active_scripts(db_session, seeded_tenant):
    from app.models.script import ScriptTemplate
    s = ScriptTemplate(
        tenant_id=seeded_tenant.id,
        title="t", trigger_intent="经济困难", content="可以分期", version=1, is_active=True,
    )
    db_session.add(s)
    db_session.flush()
    result = _load_scripts(db_session, seeded_tenant.id)
    assert "经济困难" in result
    assert "可以分期" in result["经济困难"]


def test_load_scripts_excludes_inactive(db_session, seeded_tenant):
    from app.models.script import ScriptTemplate
    s = ScriptTemplate(
        tenant_id=seeded_tenant.id,
        title="inactive", trigger_intent="其他", content="内容", version=1, is_active=False,
    )
    db_session.add(s)
    db_session.flush()
    result = _load_scripts(db_session, seeded_tenant.id)
    assert "其他" not in result or "内容" not in result.get("其他", [])


def test_engine_confidence_filtered_by_sensitivity():
    from unittest.mock import MagicMock
    from app.services.realtime_llm import RealtimeSuggestionEngine, Suggestion
    engine = RealtimeSuggestionEngine(
        case=MagicMock(), owner=MagicMock(),
        scripts={}, sensitivity_threshold=0.85, max_per_push=3
    )
    assert engine._sensitivity_threshold == 0.85
    assert engine._max_per_push == 3
```

- [ ] **Step 2: 运行，期望 FAIL**

```bash
cd poc/backend && pytest tests/services/test_prompt_injection.py -v
# Expected: FAIL — ImportError: cannot import _build_system_prompt, _load_scripts
```

- [ ] **Step 3: 修改 `app/services/realtime_llm.py`**

在文件顶部 imports 后追加：

```python
from sqlalchemy.orm import Session

SENSITIVITY_THRESHOLD: dict[int, float] = {1: 0.85, 2: 0.75, 3: 0.65, 4: 0.55, 5: 0.45}
```

将 `RealtimeSuggestionEngine.__init__` 改为：

```python
def __init__(
    self,
    case: object,
    owner: object,
    debounce_sec: Optional[int] = None,
    timeout_sec: Optional[int] = None,
    scripts: Optional[dict[str, list[str]]] = None,
    sensitivity_threshold: float = 0.65,
    max_per_push: int = 3,
):
    self._ctx = _CaseCtx(case=case, owner=owner)
    self._debounce_sec = (
        debounce_sec if debounce_sec is not None else settings.realtime_llm_debounce_sec
    )
    self._timeout_sec = (
        timeout_sec if timeout_sec is not None else settings.realtime_llm_timeout_sec
    )
    self._last_llm_at: float = time.monotonic() - self._debounce_sec
    self._scripts: dict[str, list[str]] = scripts or {}
    self._sensitivity_threshold = sensitivity_threshold
    self._max_per_push = max_per_push
    self._system_prompt: str = _build_system_prompt(
        self._scripts,
        "你是物业费催收实时辅助助手。根据业主最近一句话，给坐席生成 1 条简短话术建议。"
        "严格输出 JSON，字段：{\"text\": \"建议内容\", \"intent\": \"意图标签\", \"confidence\": 0~1}"
        "不要输出 JSON 以外的任何内容。",
    )
```

在 `_invoke_llm` 方法中，将结果过滤后返回 None 若 confidence 不达标：

```python
async def _invoke_llm(self) -> Optional[Suggestion]:
    result = await _call_llm(self._build_messages(final=False), self._system_prompt)
    confidence = float(result.get("confidence", 0.0))
    if confidence < self._sensitivity_threshold:
        return None
    intent = result.get("intent", "unknown")
    script_template_id: Optional[int] = None
    if intent in self._scripts:
        pass  # script_template_id resolved from WS message context in future
    return Suggestion(
        id=str(uuid.uuid4()),
        text=result.get("text", ""),
        intent=intent,
        confidence=confidence,
        script_template_id=script_template_id,
    )
```

在 `Suggestion` dataclass 中添加字段：

```python
@dataclass
class Suggestion:
    id: str
    text: str
    intent: str
    confidence: float
    script_template_id: Optional[int] = None

    def to_message(self) -> dict:
        msg = {
            "type": "suggestion.ready",
            "id": self.id,
            "text": self.text,
            "intent": self.intent,
            "confidence": self.confidence,
        }
        if self.script_template_id is not None:
            msg["script_template_id"] = self.script_template_id
        return msg
```

在 `_build_messages` 中使用 `self._system_prompt`（移除旧的内联 system 字符串）。

在 `_call_llm` 函数签名改为接收 `system_prompt` 参数：

```python
async def _call_llm(messages: list[dict], system_prompt: str) -> dict:
    ...
    # 在 api 分支里将旧的 system 字符串改为使用传入的 system_prompt
```

在文件末尾添加这两个模块级函数：

```python
def _load_scripts(db: Session, tenant_id: Optional[int]) -> dict[str, list[str]]:
    from sqlalchemy import select, or_
    from app.models.script import ScriptTemplate
    rows = db.execute(
        select(ScriptTemplate)
        .where(
            ScriptTemplate.is_active.is_(True),
            or_(
                ScriptTemplate.tenant_id == tenant_id,
                ScriptTemplate.tenant_id.is_(None),
            ),
        )
        .order_by(ScriptTemplate.trigger_intent)
    ).scalars().all()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row.trigger_intent, []).append(row.content)
    return result


def _build_system_prompt(scripts: dict[str, list[str]], base_prompt: str) -> str:
    if not scripts:
        return base_prompt
    sections = []
    for intent, contents in scripts.items():
        examples = "\n".join(f"  - 「{c[:80]}」" for c in contents[:3])
        sections.append(f"[参考话术 - {intent}]\n{examples}")
    script_block = "\n\n".join(sections)
    return f"{base_prompt}\n\n{script_block}"
```

- [ ] **Step 4: 修改 `app/ws/call_session.py` — start() 加载脚本与配置**

在 `start()` 方法中，在创建 `self._llm_engine` 之前添加：

```python
async def start(self, db: Session) -> None:
    call = db.get(CallRecord, self.call_id)
    if not call or not call.case_id:
        return
    case = db.get(CollectionCase, call.case_id)
    owner = db.get(OwnerProfile, case.owner_id) if case and case.owner_id else None

    from app.services.realtime_llm import _load_scripts, SENSITIVITY_THRESHOLD
    from app.models.script import TenantSuggestionConfig
    from sqlalchemy import select

    scripts = _load_scripts(db, call.tenant_id)
    cfg = db.execute(
        select(TenantSuggestionConfig).where(
            TenantSuggestionConfig.tenant_id == call.tenant_id
        )
    ).scalar_one_or_none()
    sensitivity = SENSITIVITY_THRESHOLD.get(cfg.sensitivity if cfg else 3, 0.65)
    max_per_push = cfg.max_per_push if cfg else 3

    self._llm_engine = RealtimeSuggestionEngine(
        case=case, owner=owner,
        scripts=scripts,
        sensitivity_threshold=sensitivity,
        max_per_push=max_per_push,
    )
    ...  # rest unchanged
```

- [ ] **Step 5: 运行测试，期望 PASS**

```bash
cd poc/backend && pytest tests/services/test_prompt_injection.py -v
```

- [ ] **Step 6: 运行全量测试确认无回归**

```bash
cd poc/backend && pytest tests/ -v -x
```

- [ ] **Step 7: Commit**

```bash
git add poc/backend/app/services/realtime_llm.py poc/backend/app/ws/call_session.py poc/backend/tests/services/test_prompt_injection.py
git commit -m "feat(5b-T10): inject scripts into LLM prompt + sensitivity threshold + max_per_push"
```

---

## Task 11: calls_v1.py — tag 后推断信号 + feedback 写 script_template_id

**Files:**
- Modify: `poc/backend/app/api/calls_v1.py`

- [ ] **Step 1: 修改 `patch_call_tag`**

在 `db.commit()` 之后（返回 `CallTagOut` 之前）追加：

```python
    # 推断业务信号
    if body.intent:
        from app.services.signal_inference import infer_signals_for_call
        infer_signals_for_call(call.id, body.intent, db)
        db.commit()
```

- [ ] **Step 2: 修改 `post_suggestion_feedback` — 写 script_template_id 并增 usage_count**

找到 `fb = SuggestionFeedback(...)` 那段，加 `script_template_id=body.script_template_id`：

```python
    fb = SuggestionFeedback(
        call_id=call_id,
        suggestion_id=suggestion_id,
        user_id=user_id,
        action=body.action,
        suggestion_text=body.suggestion_text or "",
        script_template_id=body.script_template_id,
    )
    db.add(fb)
    db.flush()

    # 采用时累计 usage_count
    if body.action == "adopt" and body.script_template_id is not None:
        from app.models.script import ScriptTemplate
        from sqlalchemy import update as sa_update
        db.execute(
            sa_update(ScriptTemplate)
            .where(ScriptTemplate.id == body.script_template_id)
            .values(usage_count=ScriptTemplate.usage_count + 1)
        )

    db.commit()
    return {"id": fb.id}
```

- [ ] **Step 3: 写回归测试（追加到 test_suggestion_feedback.py）**

在 `poc/backend/tests/api/test_suggestion_feedback.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_feedback_with_script_template_id_increments_usage(
    client, agent_auth_headers, seeded_call_processed, db_session, seeded_tenant
):
    from app.models.script import ScriptTemplate
    script = ScriptTemplate(
        tenant_id=seeded_tenant.id, title="t", trigger_intent="其他", content="c", version=1
    )
    db_session.add(script)
    db_session.flush()

    resp = await client.post(
        f"/api/v1/calls/{seeded_call_processed.id}/suggestions/sug-st-01/feedback",
        json={"action": "adopt", "script_template_id": script.id},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201

    db_session.expire(script)
    assert script.usage_count == 1
```

- [ ] **Step 4: 运行测试**

```bash
cd poc/backend && pytest tests/api/test_suggestion_feedback.py tests/api/test_call_tag_patch.py -v
```

- [ ] **Step 5: Commit**

```bash
git add poc/backend/app/api/calls_v1.py poc/backend/tests/api/test_suggestion_feedback.py
git commit -m "feat(5b-T11): infer signals after tag + script_template_id + usage_count"
```

---

## Task 12: Celery 夜间评分任务

**Files:**
- Create: `poc/backend/app/worker/tasks/script_grading.py`
- Create: `poc/backend/tests/worker/test_script_grading.py`

- [ ] **Step 1: 写失败测试**

```python
# poc/backend/tests/worker/test_script_grading.py
import os
import pytest

os.environ.setdefault("ASR_BACKEND", "mock")
os.environ.setdefault("LLM_BACKEND", "mock")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "True")


def _make_feedbacks(db, call_id, script_id, user_id, adopts: int, ignores: int, signals: list[int]):
    from app.models.call import SuggestionFeedback
    for i in range(adopts):
        fb = SuggestionFeedback(
            call_id=call_id, suggestion_id=f"s-a-{i}-{script_id}",
            user_id=user_id, action="adopt",
            suggestion_text="t", script_template_id=script_id,
            inferred_signal=signals[i] if i < len(signals) else 0,
        )
        db.add(fb)
    for i in range(ignores):
        fb = SuggestionFeedback(
            call_id=call_id, suggestion_id=f"s-i-{i}-{script_id}",
            user_id=user_id, action="ignore",
            suggestion_text="t", script_template_id=script_id,
        )
        db.add(fb)
    db.flush()


@pytest.fixture
def grading_setup(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from datetime import datetime, timezone
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord
    from app.models.script import ScriptTemplate

    call = CallRecord(
        tenant_id=seeded_tenant.id, case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700009999"),
        initiated_by="app", status="processed",
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(call)
    db_session.flush()
    return call, seeded_member_user


def test_grade_a_script(db_session, grading_setup):
    call, user = grading_setup
    from app.models.script import ScriptTemplate
    script = ScriptTemplate(title="高质量话术", trigger_intent="经济困难",
                            content="c", version=1, is_active=True, usage_count=30)
    db_session.add(script)
    db_session.flush()
    # 25 adopts / 5 ignores = adoption_rate=0.833 → A
    _make_feedbacks(db_session, call.id, script.id, user.id, 25, 5, [1]*10)
    db_session.commit()

    from app.worker.tasks.script_grading import compute_script_grades
    compute_script_grades()

    db_session.expire(script)
    assert script.score_grade == "A"
    assert script.adoption_rate is not None


def test_grade_d_auto_disables(db_session, grading_setup):
    call, user = grading_setup
    from app.models.script import ScriptTemplate
    script = ScriptTemplate(title="低效话术", trigger_intent="其他",
                            content="c", version=1, is_active=True, usage_count=25)
    db_session.add(script)
    db_session.flush()
    # 3 adopts / 22 ignores = adoption_rate=0.12 → D，usage_count>=20 → 自动禁用
    _make_feedbacks(db_session, call.id, script.id, user.id, 3, 22, [])
    db_session.commit()

    from app.worker.tasks.script_grading import compute_script_grades
    compute_script_grades()

    db_session.expire(script)
    assert script.score_grade == "D"
    assert script.is_active is False
```

- [ ] **Step 2: 运行，期望 FAIL**

```bash
cd poc/backend && pytest tests/worker/test_script_grading.py -v
# Expected: FAIL — ImportError
```

- [ ] **Step 3: 实现 `app/worker/tasks/script_grading.py`**

```python
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def _get_session_factory():
    global _engine, _SessionLocal
    if _engine is None:
        url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://autoluyin:autoluyin_dev@postgres:5432/autoluyin",
        )
        _engine = create_engine(url)
        _SessionLocal = sessionmaker(_engine)
    return _SessionLocal


@contextmanager
def _get_db() -> Generator[Session, None, None]:
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@celery_app.task(name="tasks.compute_script_grades")
def compute_script_grades() -> None:
    from datetime import datetime, timedelta, timezone
    from app.models.call import SuggestionFeedback
    from app.models.script import ScriptTemplate

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    with _get_db() as db:
        scripts = db.execute(select(ScriptTemplate)).scalars().all()
        for script in scripts:
            stats = db.execute(
                select(
                    func.count(SuggestionFeedback.id).label("total"),
                    func.sum(
                        (SuggestionFeedback.action == "adopt").cast(int)
                    ).label("adopted"),
                    func.count(func.distinct(SuggestionFeedback.call_id)).label("calls"),
                    func.sum(
                        (SuggestionFeedback.inferred_signal == 1).cast(int)
                    ).label("positive"),
                ).where(
                    SuggestionFeedback.script_template_id == script.id,
                    SuggestionFeedback.created_at >= cutoff,
                )
            ).one()

            total = stats.total or 0
            adopted = stats.adopted or 0
            calls = stats.calls or 0
            positive = stats.positive or 0

            if total == 0:
                continue

            adoption_rate = adopted / total
            conversion_rate = positive / calls if calls > 0 else 0.0
            script.adoption_rate = adoption_rate
            script.conversion_rate = conversion_rate

            if adoption_rate >= 0.60:
                grade = "A"
            elif adoption_rate >= 0.40:
                grade = "B"
            elif adoption_rate >= 0.20:
                grade = "C"
            else:
                grade = "D"

            script.score_grade = grade

            if grade == "D" and script.usage_count >= 20 and script.is_active:
                script.is_active = False
                logger.info(
                    "script %d auto-disabled (grade=D, usage_count=%d)",
                    script.id, script.usage_count,
                )
```

- [ ] **Step 4: 运行测试，期望 PASS**

```bash
cd poc/backend && pytest tests/worker/test_script_grading.py -v
```

- [ ] **Step 5: 运行全量后端测试**

```bash
cd poc/backend && pytest tests/ -v --cov=app --cov-report=term-missing
# Expected: all PASS，脚本库相关模块覆盖率 ≥ 85%
```

- [ ] **Step 6: Commit**

```bash
git add poc/backend/app/worker/tasks/script_grading.py poc/backend/tests/worker/test_script_grading.py
git commit -m "feat(5b-T12): Celery grading task A/B/C/D + auto-disable grade-D"
```


---

## Task 13: 前端 — 话术库列表页 + ScriptSheet 抽屉

**Files:**
- Create: `frontend/src/pages/admin/scripts/helpers.ts`
- Create: `frontend/src/pages/admin/scripts/list.tsx`
- Create: `frontend/src/pages/admin/scripts/ScriptSheet.tsx`
- Create: `frontend/src/pages/admin/scripts/__tests__/helpers.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// frontend/src/pages/admin/scripts/__tests__/helpers.test.ts
import { describe, it, expect } from "vitest";
import { getScoreGradeColor, formatAdoptionRate } from "../helpers";

describe("getScoreGradeColor", () => {
  it("returns green for A", () => {
    expect(getScoreGradeColor("A")).toContain("green");
  });
  it("returns blue for B", () => {
    expect(getScoreGradeColor("B")).toContain("blue");
  });
  it("returns orange for C", () => {
    expect(getScoreGradeColor("C")).toContain("orange");
  });
  it("returns red for D", () => {
    expect(getScoreGradeColor("D")).toContain("red");
  });
  it("returns gray for null", () => {
    expect(getScoreGradeColor(null)).toContain("gray");
  });
});

describe("formatAdoptionRate", () => {
  it("formats as percentage", () => {
    expect(formatAdoptionRate(0.753)).toBe("75.3%");
  });
  it("returns dash for null", () => {
    expect(formatAdoptionRate(null)).toBe("—");
  });
});
```

- [ ] **Step 2: 运行，期望 FAIL**

```bash
cd frontend && npx vitest run src/pages/admin/scripts/__tests__/helpers.test.ts
# Expected: FAIL — Cannot find module '../helpers'
```

- [ ] **Step 3: 实现 `helpers.ts`**

```typescript
// frontend/src/pages/admin/scripts/helpers.ts
export function getScoreGradeColor(grade: string | null): string {
  switch (grade) {
    case "A": return "text-green-700 bg-green-50 border-green-200";
    case "B": return "text-blue-700 bg-blue-50 border-blue-200";
    case "C": return "text-orange-700 bg-orange-50 border-orange-200";
    case "D": return "text-red-700 bg-red-50 border-red-200";
    default:  return "text-gray-500 bg-gray-50 border-gray-200";
  }
}

export function formatAdoptionRate(rate: number | null): string {
  if (rate === null || rate === undefined) return "—";
  return `${(rate * 100).toFixed(1)}%`;
}

export const TRIGGER_INTENTS = [
  "房屋质量",
  "经济困难",
  "服务不满",
  "联系困难",
  "其他",
] as const;

export type TriggerIntent = typeof TRIGGER_INTENTS[number];
```

- [ ] **Step 4: 运行测试，期望 PASS**

```bash
cd frontend && npx vitest run src/pages/admin/scripts/__tests__/helpers.test.ts
```

- [ ] **Step 5: 实现 `list.tsx`**

```tsx
// frontend/src/pages/admin/scripts/list.tsx
import { useCreate, useUpdate, useDelete, useGo, useList } from "@refinedev/core";
import type { CrudFilter } from "@refinedev/core";
import { Plus, Upload, History, ToggleLeft, ToggleRight, Trash2 } from "lucide-react";
import { useState } from "react";
import type { PaginatedResponse } from "../../../types";
import { getScoreGradeColor, formatAdoptionRate, TRIGGER_INTENTS } from "./helpers";
import { ScriptSheet } from "./ScriptSheet";

interface ScriptItem {
  id: number;
  tenant_id: number | null;
  title: string;
  trigger_intent: string;
  version: number;
  usage_count: number;
  adoption_rate: number | null;
  conversion_rate: number | null;
  score_grade: string | null;
  is_active: boolean;
  content: string;
  notes: string | null;
}

export function ScriptListPage() {
  const go = useGo();
  const [keyword, setKeyword] = useState("");
  const [intent, setIntent] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editScript, setEditScript] = useState<ScriptItem | null>(null);
  const PAGE_SIZE = 20;

  const filters: CrudFilter[] = [];
  if (keyword) filters.push({ field: "q", operator: "eq", value: keyword });
  if (intent) filters.push({ field: "intent", operator: "eq", value: intent });
  if (status) filters.push({ field: "status", operator: "eq", value: status });

  const { query } = useList<ScriptItem>({
    resource: "admin/scripts",
    pagination: { currentPage: page, pageSize: PAGE_SIZE },
    filters,
  });

  const data = query.data?.data as unknown as PaginatedResponse<ScriptItem> | undefined;
  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const { mutate: toggle } = useCreate();
  const { mutate: del } = useDelete();

  const hasAutoDisabled = items.some((s) => s.score_grade === "D" && !s.is_active);

  return (
    <div style={{ padding: 24 }}>
      {hasAutoDisabled && (
        <div style={{
          background: "var(--color-danger-light)", color: "var(--color-danger)",
          padding: "8px 16px", borderRadius: 6, marginBottom: 16, fontSize: 14,
        }}>
          ⚠ 有话术因 D 级评分被自动禁用，请检查并决定是否删除或重写。
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        <input
          placeholder="搜索标题/内容"
          value={keyword}
          onChange={(e) => { setKeyword(e.target.value); setPage(1); }}
          style={{ padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 6, width: 200 }}
        />
        <select value={intent} onChange={(e) => { setIntent(e.target.value); setPage(1); }}
          style={{ padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 6 }}>
          <option value="">全部类型</option>
          {TRIGGER_INTENTS.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          style={{ padding: "6px 10px", border: "1px solid #d1d5db", borderRadius: 6 }}>
          <option value="">全部状态</option>
          <option value="active">启用</option>
          <option value="inactive">禁用</option>
        </select>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button onClick={() => go({ to: "/admin/scripts/import" })}
            style={{ padding: "6px 14px", background: "#f3f4f6", border: "1px solid #d1d5db", borderRadius: 6, cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
            <Upload size={14} /> 批量导入
          </button>
          <button onClick={() => { setEditScript(null); setSheetOpen(true); }}
            style={{ padding: "6px 14px", background: "var(--color-primary)", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
            <Plus size={14} /> 新增话术
          </button>
        </div>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #e5e7eb", background: "#f9fafb" }}>
            {["话术标题", "异议类型", "版本", "使用次数", "采用率", "评分", "状态", "操作"].map((h) => (
              <th key={h} style={{ padding: "10px 12px", textAlign: "left", fontWeight: 500, color: "#374151" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {query.isLoading && (
            <tr><td colSpan={8} style={{ padding: 24, textAlign: "center", color: "#9ca3af" }}>加载中…</td></tr>
          )}
          {items.map((s) => (
            <tr key={s.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
              <td style={{ padding: "10px 12px", maxWidth: 200 }}>
                <div style={{ fontWeight: 500 }}>{s.title}</div>
                {s.tenant_id === null && (
                  <span style={{ fontSize: 11, color: "#6b7280", background: "#f3f4f6", padding: "1px 6px", borderRadius: 4 }}>平台预置</span>
                )}
              </td>
              <td style={{ padding: "10px 12px" }}>{s.trigger_intent}</td>
              <td style={{ padding: "10px 12px" }}>v{s.version}</td>
              <td style={{ padding: "10px 12px" }}>{s.usage_count}</td>
              <td style={{ padding: "10px 12px" }}>{formatAdoptionRate(s.adoption_rate)}</td>
              <td style={{ padding: "10px 12px" }}>
                {s.score_grade ? (
                  <span style={{ fontSize: 12, padding: "2px 8px", borderRadius: 4, border: "1px solid", ...Object.fromEntries(
                    getScoreGradeColor(s.score_grade).split(" ").flatMap(cls => {
                      if (cls.startsWith("text-")) return [];
                      return [];
                    })
                  ) }} className={getScoreGradeColor(s.score_grade)}>
                    {s.score_grade}
                  </span>
                ) : "—"}
              </td>
              <td style={{ padding: "10px 12px" }}>
                <span style={{
                  fontSize: 12, padding: "2px 8px", borderRadius: 4,
                  background: s.is_active ? "#dcfce7" : "#f3f4f6",
                  color: s.is_active ? "#15803d" : "#6b7280",
                }}>
                  {s.is_active ? "启用" : "禁用"}
                </span>
              </td>
              <td style={{ padding: "10px 12px" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <button onClick={() => { setEditScript(s); setSheetOpen(true); }}
                    style={{ fontSize: 12, color: "var(--color-primary)", background: "none", border: "none", cursor: "pointer" }}>
                    编辑
                  </button>
                  <button onClick={() => toggle({ resource: `admin/scripts/${s.id}/toggle`, values: {} })}
                    title={s.is_active ? "禁用" : "启用"}
                    style={{ background: "none", border: "none", cursor: "pointer", color: "#6b7280" }}>
                    {s.is_active ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                  </button>
                  <button onClick={() => go({ to: `/admin/scripts/${s.id}/versions` })}
                    title="版本历史"
                    style={{ background: "none", border: "none", cursor: "pointer", color: "#6b7280" }}>
                    <History size={16} />
                  </button>
                  {!s.is_active && (
                    <button onClick={() => del({ resource: "admin/scripts", id: s.id })}
                      title="删除"
                      style={{ background: "none", border: "none", cursor: "pointer", color: "#ef4444" }}>
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {total > PAGE_SIZE && (
        <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 16 }}>
          <button disabled={page === 1} onClick={() => setPage(p => p - 1)}>上一页</button>
          <span>第 {page} 页 / 共 {Math.ceil(total / PAGE_SIZE)} 页</span>
          <button disabled={page * PAGE_SIZE >= total} onClick={() => setPage(p => p + 1)}>下一页</button>
        </div>
      )}

      <ScriptSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        script={editScript}
        onSuccess={() => { setSheetOpen(false); query.refetch(); }}
      />
    </div>
  );
}
```

- [ ] **Step 6: 实现 `ScriptSheet.tsx`**

```tsx
// frontend/src/pages/admin/scripts/ScriptSheet.tsx
import { useCreate, useUpdate } from "@refinedev/core";
import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { TRIGGER_INTENTS } from "./helpers";

interface ScriptItem {
  id: number;
  title: string;
  trigger_intent: string;
  content: string;
  notes: string | null;
  version: number;
}

interface Props {
  open: boolean;
  onClose: () => void;
  script: ScriptItem | null;
  onSuccess: () => void;
}

export function ScriptSheet({ open, onClose, script, onSuccess }: Props) {
  const [title, setTitle] = useState("");
  const [intent, setIntent] = useState(TRIGGER_INTENTS[0]);
  const [content, setContent] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  const { mutate: create, mutation: createMut } = useCreate();
  const { mutate: update, mutation: updateMut } = useUpdate();
  const isPending = createMut.isPending || updateMut.isPending;

  useEffect(() => {
    if (script) {
      setTitle(script.title);
      setIntent(script.trigger_intent as typeof TRIGGER_INTENTS[number]);
      setContent(script.content);
      setNotes(script.notes ?? "");
    } else {
      setTitle(""); setIntent(TRIGGER_INTENTS[0]); setContent(""); setNotes("");
    }
    setError("");
  }, [script, open]);

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!title.trim() || !content.trim()) {
      setError("标题和话术内容为必填项");
      return;
    }
    const values = { title, trigger_intent: intent, content, notes: notes || null };
    if (script) {
      update(
        { resource: "admin/scripts", id: script.id, values },
        { onSuccess, onError: () => setError("保存失败，请重试") },
      );
    } else {
      create(
        { resource: "admin/scripts", values },
        { onSuccess, onError: () => setError("创建失败，请重试") },
      );
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 50,
      display: "flex", justifyContent: "flex-end",
    }}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.3)" }} onClick={onClose} />
      <div style={{
        position: "relative", width: 480, height: "100%",
        background: "#fff", boxShadow: "-4px 0 24px rgba(0,0,0,0.12)",
        display: "flex", flexDirection: "column",
      }}>
        <div style={{ padding: "20px 24px", borderBottom: "1px solid #e5e7eb", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
            {script ? `编辑话术（当前 v${script.version}，保存后升为 v${script.version + 1}）` : "新增话术"}
          </h2>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer" }}><X size={20} /></button>
        </div>

        <form onSubmit={handleSubmit} style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4 }}>话术标题 *</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)}
              maxLength={128}
              style={{ width: "100%", padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14 }} />
          </div>

          <div>
            <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4 }}>异议类型 *</label>
            <select value={intent} onChange={(e) => setIntent(e.target.value as typeof intent)}
              style={{ width: "100%", padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14 }}>
              {TRIGGER_INTENTS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          <div>
            <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4 }}>话术内容 *</label>
            <textarea value={content} onChange={(e) => setContent(e.target.value)}
              rows={6}
              style={{ width: "100%", padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14, resize: "vertical" }} />
          </div>

          <div>
            <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4 }}>编写说明（可选）</label>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)}
              rows={3}
              style={{ width: "100%", padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14, resize: "vertical" }} />
          </div>

          {error && <p style={{ color: "#ef4444", fontSize: 13, margin: 0 }}>{error}</p>}
        </form>

        <div style={{ padding: "16px 24px", borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button onClick={onClose} style={{ padding: "8px 16px", background: "#f9fafb", border: "1px solid #d1d5db", borderRadius: 6, cursor: "pointer" }}>取消</button>
          <button onClick={handleSubmit} disabled={isPending}
            style={{ padding: "8px 16px", background: "var(--color-primary)", color: "#fff", border: "none", borderRadius: 6, cursor: isPending ? "not-allowed" : "pointer" }}>
            {isPending ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 7: 运行前端测试**

```bash
cd frontend && npx vitest run src/pages/admin/scripts/__tests__/helpers.test.ts
```

- [ ] **Step 8: 类型检查**

```bash
cd frontend && npx tsc --noEmit
# Expected: 0 errors
```

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/admin/scripts/
git commit -m "feat(5b-T13): admin scripts list page + ScriptSheet drawer"
```

---

## Task 14: 前端 — 版本历史页 + ImportModal

**Files:**
- Create: `frontend/src/pages/admin/scripts/versions.tsx`
- Create: `frontend/src/pages/admin/scripts/ImportModal.tsx`

- [ ] **Step 1: 实现 `versions.tsx`**

```tsx
// frontend/src/pages/admin/scripts/versions.tsx
import { useOne, useCreate, useGo } from "@refinedev/core";
import { useParams } from "react-router-dom";
import { useState } from "react";
import { ArrowLeft, RotateCcw, ChevronDown, ChevronUp } from "lucide-react";

interface VersionItem {
  version: number;
  title: string;
  trigger_intent: string;
  content: string;
  notes: string | null;
  edited_by: number | null;
  edited_at: string;
}

interface ScriptDetail {
  id: number;
  title: string;
  version: number;
}

export function ScriptVersionsPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const scriptId = Number(id);
  const [expandedVersion, setExpandedVersion] = useState<number | null>(null);
  const [confirmVersion, setConfirmVersion] = useState<number | null>(null);
  const [rollbackError, setRollbackError] = useState("");

  const { query: scriptQuery } = useOne<ScriptDetail>({
    resource: "admin/scripts", id: scriptId,
  });
  const { query: versionsQuery } = useOne<VersionItem[]>({
    resource: `admin/scripts/${scriptId}`, id: "versions",
  });

  const { mutate: rollback, mutation: rollbackMut } = useCreate();
  const script = scriptQuery.data?.data;
  const versions: VersionItem[] = (versionsQuery.data?.data as unknown as VersionItem[]) ?? [];

  const handleRollback = (toVersion: number) => {
    setRollbackError("");
    rollback(
      { resource: `admin/scripts/${scriptId}/rollback`, values: { to_version: toVersion } },
      {
        onSuccess: () => { setConfirmVersion(null); go({ to: `/admin/scripts` }); },
        onError: () => setRollbackError("回滚失败，请重试"),
      },
    );
  };

  return (
    <div style={{ padding: 24, maxWidth: 800 }}>
      <button onClick={() => go({ to: "/admin/scripts" })}
        style={{ display: "flex", alignItems: "center", gap: 6, background: "none", border: "none", cursor: "pointer", color: "#6b7280", marginBottom: 16 }}>
        <ArrowLeft size={16} /> 返回话术库
      </button>

      <h2 style={{ margin: "0 0 4px", fontSize: 20, fontWeight: 600 }}>
        {script?.title ?? "…"} — 版本历史
      </h2>
      <p style={{ margin: "0 0 24px", color: "#6b7280", fontSize: 13 }}>
        当前版本：v{script?.version}
      </p>

      {versions.map((v) => (
        <div key={v.version} style={{
          border: "1px solid #e5e7eb", borderRadius: 8, marginBottom: 12, overflow: "hidden",
        }}>
          <div style={{
            display: "flex", alignItems: "center", padding: "12px 16px",
            background: "#f9fafb", cursor: "pointer",
          }} onClick={() => setExpandedVersion(expandedVersion === v.version ? null : v.version)}>
            <div style={{ flex: 1 }}>
              <span style={{ fontWeight: 600, marginRight: 12 }}>v{v.version}</span>
              <span style={{ color: "#6b7280", fontSize: 13 }}>{v.edited_at.slice(0, 10)}</span>
              <span style={{ marginLeft: 12, color: "#374151", fontSize: 14 }}>
                {v.content.slice(0, 80)}{v.content.length > 80 ? "…" : ""}
              </span>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {v.version !== script?.version && (
                <button
                  onClick={(e) => { e.stopPropagation(); setConfirmVersion(v.version); }}
                  style={{ fontSize: 12, padding: "4px 10px", background: "#fef3c7", color: "#92400e", border: "1px solid #fde68a", borderRadius: 4, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
                  <RotateCcw size={12} /> 回滚到此版本
                </button>
              )}
              {expandedVersion === v.version ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </div>
          </div>
          {expandedVersion === v.version && (
            <div style={{ padding: "16px", borderTop: "1px solid #e5e7eb", fontSize: 14 }}>
              <div style={{ marginBottom: 8 }}><strong>标题：</strong>{v.title}</div>
              <div style={{ marginBottom: 8 }}><strong>类型：</strong>{v.trigger_intent}</div>
              <div style={{ marginBottom: 8, whiteSpace: "pre-wrap" }}><strong>内容：</strong>{v.content}</div>
              {v.notes && <div><strong>说明：</strong>{v.notes}</div>}
            </div>
          )}
        </div>
      ))}

      {/* Rollback Confirm Dialog */}
      {confirmVersion !== null && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 60 }}>
          <div style={{ background: "#fff", borderRadius: 10, padding: 24, maxWidth: 400, width: "90%" }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 16 }}>确认回滚</h3>
            <p style={{ margin: "0 0 16px", fontSize: 14, color: "#374151" }}>
              将覆盖当前 v{script?.version}，生成 v{(script?.version ?? 0) + 1}，确认继续？
            </p>
            {rollbackError && <p style={{ color: "#ef4444", fontSize: 13 }}>{rollbackError}</p>}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button onClick={() => setConfirmVersion(null)}
                style={{ padding: "8px 16px", background: "#f9fafb", border: "1px solid #d1d5db", borderRadius: 6, cursor: "pointer" }}>取消</button>
              <button onClick={() => handleRollback(confirmVersion)}
                disabled={rollbackMut.isPending}
                style={{ padding: "8px 16px", background: "#f59e0b", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer" }}>
                {rollbackMut.isPending ? "回滚中…" : "确认回滚"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 实现 `ImportModal.tsx`**

```tsx
// frontend/src/pages/admin/scripts/ImportModal.tsx
import { useApiUrl } from "@refinedev/core";
import { useState, useRef } from "react";
import { X, Upload, Download } from "lucide-react";

interface ImportResult {
  success: number;
  skipped: number;
  failed: number;
  errors: string[];
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function ImportModal({ open, onClose, onSuccess }: Props) {
  const apiUrl = useApiUrl();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

  const handleImport = async () => {
    if (!file) return;
    setError("");
    setLoading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const token = localStorage.getItem("token") ?? "";
      const resp = await fetch(`${apiUrl}/admin/scripts/import`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const body = await resp.json();
      if (!resp.ok) {
        setError(body?.detail?.message ?? "导入失败");
      } else {
        setResult(body as ImportResult);
        if ((body as ImportResult).success > 0) onSuccess();
      }
    } catch {
      setError("网络错误，请重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 60 }}>
      <div style={{ background: "#fff", borderRadius: 10, padding: 24, width: 480, maxWidth: "92vw" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>批量导入话术</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer" }}><X size={18} /></button>
        </div>

        {!result ? (
          <>
            <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
              模板列顺序：话术标题 / 异议类型 / 话术内容 / 编写说明（可选）
            </p>
            <div
              onClick={() => inputRef.current?.click()}
              style={{
                border: "2px dashed #d1d5db", borderRadius: 8, padding: "32px 24px",
                textAlign: "center", cursor: "pointer", color: "#6b7280",
                background: file ? "#f0fdf4" : "#fafafa",
              }}>
              <Upload size={24} style={{ margin: "0 auto 8px", display: "block" }} />
              {file ? <span style={{ color: "#15803d" }}>{file.name}</span> : "点击或拖拽上传 .xlsx 文件"}
            </div>
            <input ref={inputRef} type="file" accept=".xlsx,.xls" style={{ display: "none" }}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)} />

            {error && <p style={{ color: "#ef4444", fontSize: 13, marginTop: 8 }}>{error}</p>}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
              <button onClick={onClose}
                style={{ padding: "8px 16px", background: "#f9fafb", border: "1px solid #d1d5db", borderRadius: 6, cursor: "pointer" }}>取消</button>
              <button onClick={handleImport} disabled={!file || loading}
                style={{ padding: "8px 16px", background: "var(--color-primary)", color: "#fff", border: "none", borderRadius: 6, cursor: (!file || loading) ? "not-allowed" : "pointer" }}>
                {loading ? "导入中…" : "确认导入"}
              </button>
            </div>
          </>
        ) : (
          <>
            <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 16, marginBottom: 12 }}>
              <div style={{ color: "#15803d", fontWeight: 600, marginBottom: 4 }}>导入完成</div>
              <div style={{ fontSize: 14, color: "#374151" }}>
                成功：{result.success} 条 &nbsp;|&nbsp; 跳过：{result.skipped} 条 &nbsp;|&nbsp; 失败：{result.failed} 条
              </div>
            </div>
            {result.errors.length > 0 && (
              <ul style={{ fontSize: 12, color: "#ef4444", paddingLeft: 16, margin: "0 0 12px" }}>
                {result.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            )}
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button onClick={onClose}
                style={{ padding: "8px 16px", background: "var(--color-primary)", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer" }}>关闭</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 类型检查**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/admin/scripts/versions.tsx frontend/src/pages/admin/scripts/ImportModal.tsx
git commit -m "feat(5b-T14): script versions page + ImportModal"
```

---

## Task 15: 前端 — 督导话术标注页

**Files:**
- Create: `frontend/src/pages/supervisor/helpers.ts`
- Create: `frontend/src/pages/supervisor/script-labels.tsx`
- Create: `frontend/src/pages/supervisor/__tests__/helpers.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// frontend/src/pages/supervisor/__tests__/helpers.test.ts
import { describe, it, expect } from "vitest";
import { getLabelStatus } from "../helpers";

describe("getLabelStatus", () => {
  it("returns unlabeled when no supervisor_label", () => {
    expect(getLabelStatus(null)).toBe("unlabeled");
  });
  it("returns good", () => {
    expect(getLabelStatus("good")).toBe("good");
  });
  it("returns bad", () => {
    expect(getLabelStatus("bad")).toBe("bad");
  });
});
```

- [ ] **Step 2: 实现 `helpers.ts`**

```typescript
// frontend/src/pages/supervisor/helpers.ts
export type LabelStatus = "unlabeled" | "good" | "bad";

export function getLabelStatus(label: string | null): LabelStatus {
  if (!label) return "unlabeled";
  if (label === "good") return "good";
  return "bad";
}
```

- [ ] **Step 3: 运行测试，期望 PASS**

```bash
cd frontend && npx vitest run src/pages/supervisor/__tests__/helpers.test.ts
```

- [ ] **Step 4: 实现 `script-labels.tsx`**

```tsx
// frontend/src/pages/supervisor/script-labels.tsx
import { useList, useCreate } from "@refinedev/core";
import { useState } from "react";
import { X } from "lucide-react";
import { getLabelStatus } from "./helpers";

interface LabelItem {
  feedback_id: number;
  call_id: number;
  suggestion_text: string;
  supervisor_label: string | null;
  supervisor_note: string | null;
  script_template_id: number | null;
  created_at: string;
}

export function SupervisorScriptLabelsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [modalFb, setModalFb] = useState<LabelItem | null>(null);
  const [labelChoice, setLabelChoice] = useState<"good" | "bad">("good");
  const [note, setNote] = useState("");
  const [noteError, setNoteError] = useState("");

  const { query } = useList<LabelItem>({
    resource: "supervisor/script-labels",
    filters: unreadOnly ? [{ field: "unread_only", operator: "eq", value: true }] : [],
  });

  const items: LabelItem[] = (query.data?.data as unknown as LabelItem[]) ?? [];
  const { mutate: submitLabel, mutation: submitMut } = useCreate();

  const handleSubmit = () => {
    setNoteError("");
    if (labelChoice === "bad" && !note.trim()) {
      setNoteError("差话术标注必须填写点评");
      return;
    }
    if (!modalFb) return;
    submitLabel(
      {
        resource: `supervisor/script-labels/${modalFb.feedback_id}`,
        values: { label: labelChoice, note: note || null },
      },
      {
        onSuccess: () => { setModalFb(null); query.refetch(); },
        onError: () => setNoteError("提交失败，请重试"),
      },
    );
  };

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>话术标注</h2>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14, cursor: "pointer" }}>
          <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} />
          仅看未标注
        </label>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #e5e7eb", background: "#f9fafb" }}>
            {["话术内容", "通话 ID", "时间", "坐席反馈", "督导标注"].map((h) => (
              <th key={h} style={{ padding: "10px 12px", textAlign: "left", fontWeight: 500 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const status = getLabelStatus(item.supervisor_label);
            return (
              <tr key={item.feedback_id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={{ padding: "10px 12px", maxWidth: 300 }}>
                  {item.suggestion_text.slice(0, 80)}{item.suggestion_text.length > 80 ? "…" : ""}
                </td>
                <td style={{ padding: "10px 12px" }}>{item.call_id}</td>
                <td style={{ padding: "10px 12px" }}>{item.created_at.slice(0, 10)}</td>
                <td style={{ padding: "10px 12px" }}>—</td>
                <td style={{ padding: "10px 12px" }}>
                  {status === "unlabeled" ? (
                    <div style={{ display: "flex", gap: 6 }}>
                      <button onClick={() => { setModalFb(item); setLabelChoice("good"); setNote(""); setNoteError(""); }}
                        style={{ padding: "4px 10px", background: "#dcfce7", color: "#15803d", border: "1px solid #bbf7d0", borderRadius: 4, cursor: "pointer", fontSize: 12 }}>好话术</button>
                      <button onClick={() => { setModalFb(item); setLabelChoice("bad"); setNote(""); setNoteError(""); }}
                        style={{ padding: "4px 10px", background: "#fee2e2", color: "#b91c1c", border: "1px solid #fecaca", borderRadius: 4, cursor: "pointer", fontSize: 12 }}>差话术</button>
                    </div>
                  ) : (
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{
                        padding: "2px 8px", borderRadius: 4, fontSize: 12,
                        background: status === "good" ? "#dcfce7" : "#fee2e2",
                        color: status === "good" ? "#15803d" : "#b91c1c",
                      }}>
                        {status === "good" ? "好话术" : "差话术"}
                      </span>
                      <button onClick={() => { setModalFb(item); setLabelChoice(item.supervisor_label as "good" | "bad"); setNote(item.supervisor_note ?? ""); setNoteError(""); }}
                        style={{ fontSize: 12, color: "#6b7280", background: "none", border: "none", cursor: "pointer" }}>修改</button>
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Label Modal */}
      {modalFb && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 60 }}>
          <div style={{ background: "#fff", borderRadius: 10, padding: 24, width: 400, maxWidth: "92vw" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <h3 style={{ margin: 0, fontSize: 16 }}>话术标注</h3>
              <button onClick={() => setModalFb(null)} style={{ background: "none", border: "none", cursor: "pointer" }}><X size={18} /></button>
            </div>
            <p style={{ fontSize: 13, color: "#374151", marginBottom: 12 }}>{modalFb.suggestion_text.slice(0, 120)}</p>

            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              {(["good", "bad"] as const).map((l) => (
                <button key={l} onClick={() => setLabelChoice(l)}
                  style={{
                    flex: 1, padding: "8px", borderRadius: 6, cursor: "pointer", fontSize: 14,
                    border: labelChoice === l ? "2px solid var(--color-primary)" : "1px solid #d1d5db",
                    background: labelChoice === l ? "var(--color-primary-light)" : "#fff",
                    fontWeight: labelChoice === l ? 600 : 400,
                  }}>
                  {l === "good" ? "好话术" : "差话术"}
                </button>
              ))}
            </div>

            {labelChoice === "bad" && (
              <div style={{ marginBottom: 12 }}>
                <label style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4 }}>点评（差话术必填）</label>
                <textarea value={note} onChange={(e) => setNote(e.target.value)}
                  rows={3} style={{ width: "100%", padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 6, fontSize: 14, resize: "vertical" }} />
              </div>
            )}

            {noteError && <p style={{ color: "#ef4444", fontSize: 12, margin: "0 0 8px" }}>{noteError}</p>}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button onClick={() => setModalFb(null)}
                style={{ padding: "8px 16px", background: "#f9fafb", border: "1px solid #d1d5db", borderRadius: 6, cursor: "pointer" }}>取消</button>
              <button onClick={handleSubmit} disabled={submitMut.isPending}
                style={{ padding: "8px 16px", background: "var(--color-primary)", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer" }}>
                {submitMut.isPending ? "提交中…" : "提交"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: 运行测试 + 类型检查**

```bash
cd frontend && npx vitest run src/pages/supervisor/__tests__/helpers.test.ts && npx tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/supervisor/
git commit -m "feat(5b-T15): supervisor script-labels page"
```

---

## Task 16: App.tsx 路由注册 + 收尾验证

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 修改 App.tsx**

在 `import` 区块追加：

```tsx
import { ScriptListPage } from "./pages/admin/scripts/list";
import { ScriptVersionsPage } from "./pages/admin/scripts/versions";
import { SupervisorScriptLabelsPage } from "./pages/supervisor/script-labels";
```

在 `resources` 数组追加：

```tsx
{
  name: "admin/scripts",
  list: "/admin/scripts",
  show: "/admin/scripts/:id/versions",
},
{
  name: "supervisor/script-labels",
  list: "/supervisor/script-labels",
},
```

在 `<Routes>` 中的 protected 区块追加（与现有 admin/supervisor routes 同级）：

```tsx
<Route path="/admin/scripts" element={<ScriptListPage />} />
<Route path="/admin/scripts/:id/versions" element={<ScriptVersionsPage />} />
<Route path="/supervisor/script-labels" element={<SupervisorScriptLabelsPage />} />
```

- [ ] **Step 2: 运行全量前端测试**

```bash
cd frontend && npx vitest run
# Expected: all PASS
```

- [ ] **Step 3: 全量后端测试**

```bash
cd poc/backend && pytest tests/ -v --cov=app --cov-report=term-missing
# Expected: all PASS，话术库相关覆盖率 ≥ 85%
```

- [ ] **Step 4: Lint**

```bash
cd poc/backend && ruff check .
cd frontend && npm run lint
```

- [ ] **Step 5: 类型检查**

```bash
cd poc/backend && mypy app/
cd frontend && npx tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(5b-T16): register script library + supervisor label routes in App.tsx"
```

- [ ] **Step 7: 调用 finishing-a-development-branch skill**

跑完所有测试后，使用 `finishing-a-development-branch` skill 进行推送 + PR 流程。

---

## 自查清单（Spec Coverage）

| Spec 章节 | 对应 Task | 状态 |
|-----------|-----------|------|
| §2.1 script_template | T1, T2 | — |
| §2.2 script_template_version | T1, T2 | — |
| §2.3 tenant_suggestion_config | T1, T2 | — |
| §2.4 suggestion_feedback 5 列 | T1, T2 | — |
| §3.1 Admin CRUD + 版本 + 回滚 | T5 | — |
| §3.1 Excel 导入 | T6 | — |
| §3.2 督导标注 | T7 | — |
| §3.3 推送配置 | T8 | — |
| §3.4 Pydantic schemas | T3 | — |
| §4 Prompt 注入 + _load_scripts | T10 | — |
| §4.3 灵敏度控制 | T10 | — |
| §4.4 usage_count 累计 | T11 | — |
| §5 业务信号推断 | T4, T11 | — |
| §6 Celery 夜间评分 | T12 | — |
| §7 Excel 导入规范 | T6 | — |
| §8.1-8.4 Admin 前端页面 | T13, T14, T16 | — |
| §8.5 督导标注前端页面 | T15, T16 | — |
| §9 测试覆盖目标 | T1-T16 各自测试 | — |

