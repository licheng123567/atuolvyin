# Sprint 3b Implementation Plan — ASR Pipeline + Frontend + Android

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the Celery pipeline to run ASR → LLM analysis after recording upload, add case/call detail API endpoints, build PC frontend detail pages, and migrate Android to JWT-authenticated v1 endpoints.

**Architecture:** Single sequential Celery task (mock ASR + mock LLM in tests via `ASR_BACKEND=mock` / `LLM_BACKEND=mock` already set in conftest); LLM fields stored in `AnalysisResult.key_segments` JSON; frontend uses Refine `useOne`/`useList` hooks; Android migrates to `/api/v1/` + OkHttp JWT interceptor.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Celery + pytest + httpx (backend); React + Refine.dev + Tailwind (frontend); Kotlin + OkHttp3 + Retrofit2 (Android)

---

## ⚠️ Test Isolation Notes (read before writing any tests)

**Known conflict:** `tests/worker/test_process_call.py` has `test_process_call_sets_status_queued` which asserts `status == "queued"`. After Task 2 expands the pipeline, this test **will fail** (status becomes "processed"). This test **must be updated** in Task 2.

**Pattern for pipeline tests:** Always call `process_call.run(call_id)` directly and patch `_get_db` with `_mock_db`. Never invoke the upload API endpoint in pipeline tests — `test_calls_v1.py` already has `autouse=True` `mock_process_call_delay` that covers upload API tests.

**Storage file conflicts:** Use unique `object_key` values per test fixture (include fixture IDs or use `uuid`). Clean up temp files in fixture teardown with `try/finally`.

---

## File Map

| File | Action |
|------|--------|
| `poc/backend/app/core/storage.py` | Modify — add `get_bytes()` to ABC + all 3 impls |
| `poc/backend/app/models/call.py` | Modify — add `object_key` to `CallRecord` |
| `poc/backend/alembic/versions/b7e2f19a8c30_3b_001.py` | Create — add `object_key` col + fix transcript FK |
| `poc/backend/app/api/calls_v1.py` | Modify — set `object_key` on upload; fill transcript+analysis in detail |
| `poc/backend/app/schemas/call.py` | Modify — add `TranscriptOut`, `AnalysisResultOut`; update `CallDetailResponse` |
| `poc/backend/app/schemas/case.py` | Modify — add `CaseCallItem`, `TimelineEvent`, `CaseDetailResponse`; add `phone` to `OwnerInfo` |
| `poc/backend/app/worker/tasks/call_pipeline.py` | Modify — full ASR→LLM pipeline |
| `poc/backend/app/api/admin_cases.py` | Modify — `get_case` returns `CaseDetailResponse` with calls |
| `poc/backend/app/api/agent_cases.py` | Modify — add `GET /cases/{case_id}` with phone role logic |
| `poc/backend/tests/test_storage_get_bytes.py` | Create |
| `poc/backend/tests/worker/test_process_call.py` | Modify — update broken test + add 3b pipeline tests |
| `poc/backend/tests/api/test_calls_v1_detail.py` | Create |
| `poc/backend/tests/api/test_admin_cases_detail.py` | Create |
| `poc/backend/tests/api/test_agent_cases_detail.py` | Create |
| `frontend/src/pages/admin/cases/detail.tsx` | Create |
| `frontend/src/pages/calls/detail.tsx` | Create |
| `frontend/src/pages/agent/cases/detail.tsx` | Create |
| `frontend/src/App.tsx` | Modify — add 3 new routes |
| `frontend/src/config/nav.ts` | Modify — add detail links |
| `poc/android/app/.../Api.kt` | Modify — v1 endpoints + JWT interceptor |
| `poc/android/app/.../MainActivity.kt` | Modify — persist JWT, login flow |
| `poc/android/app/.../CallWatcherService.kt` | Modify — use `case_id` |

---

## Task 1: Storage `get_bytes` + `CallRecord.object_key` + Migration + Upload Fix

**Files:**
- Modify: `poc/backend/app/core/storage.py`
- Modify: `poc/backend/app/models/call.py`
- Create: `poc/backend/alembic/versions/b7e2f19a8c30_3b_001_add_object_key_fix_transcript_fk.py`
- Modify: `poc/backend/app/api/calls_v1.py` (line 154–165: add `object_key`)
- Create: `poc/backend/tests/test_storage_get_bytes.py`

- [ ] **Step 1: Write failing test for `get_bytes`**

```python
# poc/backend/tests/test_storage_get_bytes.py
import os
import pytest


def test_local_file_storage_get_bytes():
    from app.core.storage import LocalFileStorage

    ls = LocalFileStorage()
    expected = b"sprint3b test audio bytes"
    key = "test_get_bytes/unique_sample.mp3"
    ls.put_object(key, expected, "audio/mpeg")
    result = ls.get_bytes(key)
    assert result == expected
    # cleanup
    os.unlink(ls.local_path(key))


def test_local_file_storage_get_bytes_missing_key_raises():
    from app.core.storage import LocalFileStorage

    ls = LocalFileStorage()
    with pytest.raises(FileNotFoundError):
        ls.get_bytes("nonexistent/file.mp3")
```

- [ ] **Step 2: Run test — confirm it fails**

```
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/pytest tests/test_storage_get_bytes.py -v
```

Expected: `FAILED` with `AttributeError: 'LocalFileStorage' object has no attribute 'get_bytes'`

- [ ] **Step 3: Add `get_bytes` to `storage.py`**

Replace the entire `StorageBackend` ABC + 3 implementations. In `poc/backend/app/core/storage.py`, add after each existing `get_url` method:

```python
# In StorageBackend (after get_url abstract method):
@abstractmethod
def get_bytes(self, object_key: str) -> bytes:
    """Return raw bytes of stored object. Raises on failure."""

# In LocalFileStorage (after local_path method):
def get_bytes(self, object_key: str) -> bytes:
    path = self.local_path(object_key)
    with open(path, "rb") as f:
        return f.read()

# In MinIOStorage (after get_url method):
def get_bytes(self, object_key: str) -> bytes:
    response = self._client.get_object(self._bucket, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()

# In OSSStorage (after get_url method):
def get_bytes(self, object_key: str) -> bytes:
    result = self._bucket.get_object(object_key)
    return result.read()
```

- [ ] **Step 4: Run test — confirm passes**

```
/opt/homebrew/bin/pytest tests/test_storage_get_bytes.py -v
```

Expected: `PASSED`

- [ ] **Step 5: Add `object_key` to `CallRecord` model**

In `poc/backend/app/models/call.py`, after `recording_url` line (line 34):

```python
object_key: Mapped[Optional[str]] = mapped_column(sa.Text)  # storage key for worker download
```

- [ ] **Step 6: Create Alembic migration 3b-001**

Create `poc/backend/alembic/versions/b7e2f19a8c30_3b_001_add_object_key_fix_transcript_fk.py`:

```python
"""3b_001_add_object_key_fix_transcript_fk

Revision ID: b7e2f19a8c30
Revises: f398859a9fb3
Create Date: 2026-04-30

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b7e2f19a8c30'
down_revision: Union[str, None] = 'f398859a9fb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('call_record', sa.Column('object_key', sa.Text(), nullable=True))
    # Fix transcript FK in case deployed DB has wrong target (was call_log in some envs)
    with op.batch_alter_table('transcript') as batch_op:
        try:
            batch_op.drop_constraint('transcript_call_id_fkey', type_='foreignkey')
        except Exception:
            pass
        batch_op.create_foreign_key(
            'fk_transcript_call_record', 'call_record', ['call_id'], ['id']
        )


def downgrade() -> None:
    op.drop_column('call_record', 'object_key')
```

- [ ] **Step 7: Set `object_key` in upload handler**

In `poc/backend/app/api/calls_v1.py`, in the `CallRecord(...)` constructor (around line 154), add `object_key=object_key`:

```python
    call = CallRecord(
        tenant_id=tenant_id,
        case_id=case_id,
        caller_user_id=user_id,
        callee_phone_enc=callee_phone_enc,
        initiated_by="app",
        started_at=started_dt,
        ended_at=ended_dt,
        duration_sec=duration_sec,
        recording_url=recording_url,
        object_key=object_key,
        status="uploaded",
    )
```

- [ ] **Step 8: Run full test suite — confirm no regressions**

```
/opt/homebrew/bin/pytest --tb=short -q
```

Expected: all existing tests still pass (0 new failures)

- [ ] **Step 9: Commit**

```bash
git add poc/backend/app/core/storage.py \
        poc/backend/app/models/call.py \
        poc/backend/alembic/versions/b7e2f19a8c30_3b_001_add_object_key_fix_transcript_fk.py \
        poc/backend/app/api/calls_v1.py \
        poc/backend/tests/test_storage_get_bytes.py
git commit -m "feat: add storage.get_bytes, CallRecord.object_key, alembic 3b-001"
```

---

## Task 2: Expand `process_call` Pipeline (ASR → Transcript → LLM → AnalysisResult)

**Files:**
- Modify: `poc/backend/app/worker/tasks/call_pipeline.py`
- Modify: `poc/backend/tests/worker/test_process_call.py`

> **Conflict fix:** The existing `test_process_call_sets_status_queued` expects `status == "queued"`. The expanded pipeline sets status to "processed". **This test must be updated** in Step 1 before the implementation.

- [ ] **Step 1: Update existing tests to match new behavior**

Replace the entire content of `poc/backend/tests/worker/test_process_call.py`:

```python
import os
from contextlib import contextmanager
from unittest.mock import patch

import pytest


@pytest.fixture
def seeded_call_with_recording(db_session, seeded_tenant, seeded_member_user, seeded_case):
    """Creates a CallRecord with object_key and writes a fake audio file to test storage."""
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    # Use unique key per test run to avoid cross-test file conflicts
    object_key = f"calls/{seeded_tenant.id}/test3b_{seeded_member_user.id}.mp3"
    storage_root = os.environ.get("LOCAL_STORAGE_ROOT", "/tmp/autoluyin_test_recordings")
    file_path = os.path.join(storage_root, object_key)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(b"ID3\x00" + b"\x00" * 100)  # minimal fake MP3

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        status="uploaded",
        object_key=object_key,
    )
    db_session.add(call)
    db_session.flush()

    yield call

    # cleanup file (DB rollback handles DB state)
    try:
        os.unlink(file_path)
    except OSError:
        pass


def test_process_call_full_pipeline(seeded_call_with_recording, db_session):
    """Full pipeline: mock ASR + mock LLM → status=processed, Transcript + AnalysisResult created."""
    import app.worker.tasks.call_pipeline as pipeline_module
    from sqlalchemy import select
    from app.models.call import Transcript, AnalysisResult

    @contextmanager
    def _mock_db():
        yield db_session
        db_session.flush()

    with patch.object(pipeline_module, "_get_db", _mock_db):
        pipeline_module.process_call.run(seeded_call_with_recording.id)

    db_session.refresh(seeded_call_with_recording)
    assert seeded_call_with_recording.status == "processed"

    transcript = db_session.execute(
        select(Transcript).where(Transcript.call_id == seeded_call_with_recording.id)
    ).scalar_one_or_none()
    assert transcript is not None
    assert transcript.full_text is not None
    assert transcript.asr_model == "mock"

    analysis = db_session.execute(
        select(AnalysisResult).where(AnalysisResult.call_id == seeded_call_with_recording.id)
    ).scalar_one_or_none()
    assert analysis is not None
    assert analysis.key_segments is not None
    assert "intent" in analysis.key_segments
    assert analysis.needs_review is False


def test_process_call_idempotent_on_retry(seeded_call_with_recording, db_session):
    """Running process_call twice does not create duplicate Transcript/AnalysisResult."""
    import app.worker.tasks.call_pipeline as pipeline_module
    from sqlalchemy import select, func
    from app.models.call import Transcript, AnalysisResult

    @contextmanager
    def _mock_db():
        yield db_session
        db_session.flush()

    with patch.object(pipeline_module, "_get_db", _mock_db):
        pipeline_module.process_call.run(seeded_call_with_recording.id)
    with patch.object(pipeline_module, "_get_db", _mock_db):
        pipeline_module.process_call.run(seeded_call_with_recording.id)

    count_t = db_session.execute(
        select(func.count()).where(Transcript.call_id == seeded_call_with_recording.id)
    ).scalar_one()
    count_a = db_session.execute(
        select(func.count()).where(AnalysisResult.call_id == seeded_call_with_recording.id)
    ).scalar_one()
    assert count_t == 1
    assert count_a == 1


def test_process_call_no_object_key_sets_failed(db_session, seeded_tenant, seeded_member_user, seeded_case):
    """Call with no object_key: pipeline marks status=failed and returns."""
    import app.worker.tasks.call_pipeline as pipeline_module
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800001111"),
        status="uploaded",
        object_key=None,
    )
    db_session.add(call)
    db_session.flush()

    @contextmanager
    def _mock_db():
        yield db_session
        db_session.flush()

    with patch.object(pipeline_module, "_get_db", _mock_db):
        pipeline_module.process_call.run(call.id)

    db_session.refresh(call)
    assert call.status == "failed"


def test_process_call_nonexistent_id_is_noop(db_session):
    import app.worker.tasks.call_pipeline as pipeline_module

    @contextmanager
    def _mock_db():
        yield db_session
        db_session.flush()

    with patch.object(pipeline_module, "_get_db", _mock_db):
        pipeline_module.process_call.run(999999999)  # should not raise
```

- [ ] **Step 2: Run updated tests — confirm they fail (implementation not done yet)**

```
/opt/homebrew/bin/pytest tests/worker/test_process_call.py -v
```

Expected: most tests FAIL because `process_call` still only sets `status="queued"`

- [ ] **Step 3: Implement the expanded pipeline**

Replace the entire content of `poc/backend/app/worker/tasks/call_pipeline.py`:

```python
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager, suppress
from typing import Generator, Optional

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.storage import storage
from app.services import asr, llm
from app.worker.celery_app import celery_app

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
        try:
            session.close()
        finally:
            pass


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_call(self, call_id: int) -> None:
    from app.models.call import AnalysisResult, CallRecord, Transcript
    from app.models.case import CollectionCase

    tmp_path: Optional[str] = None
    try:
        with _get_db() as db:
            call = db.get(CallRecord, call_id)
            if not call:
                return

            call.status = "queued"
            db.commit()

            if not call.object_key:
                call.status = "failed"
                return

            call.status = "processing"
            db.commit()

            # Download recording to temp file
            raw = storage.get_bytes(call.object_key)
            ext = call.object_key.rsplit(".", 1)[-1] if "." in call.object_key else "mp3"
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name

            # ASR — idempotent: skip if transcript already exists
            existing_transcript = db.execute(
                select(Transcript).where(Transcript.call_id == call_id)
            ).scalar_one_or_none()
            if existing_transcript:
                full_text = existing_transcript.full_text or ""
            else:
                asr_result = asr.transcribe(
                    audio_url=storage.get_url(call.object_key),
                    local_file_path=tmp_path,
                )
                new_transcript = Transcript(
                    call_id=call_id,
                    full_text=asr_result["full_text"],
                    segments=asr_result.get("segments"),
                    asr_model=asr_result.get("model"),
                )
                db.add(new_transcript)
                db.flush()
                full_text = asr_result["full_text"]

            # LLM — idempotent: skip if analysis already exists
            existing_analysis = db.execute(
                select(AnalysisResult).where(AnalysisResult.call_id == call_id)
            ).scalar_one_or_none()
            if not existing_analysis:
                case = db.get(CollectionCase, call.case_id) if call.case_id else None
                llm_result = llm.extract(
                    "collection",
                    {
                        "amount_owed": str(case.amount_owed or 0) if case else "0",
                        "months_overdue": str(case.months_overdue or 0) if case else "0",
                    },
                    full_text,
                )
                fields = llm_result.get("fields", {})
                summary = " · ".join(
                    p for p in [fields.get("intent"), fields.get("excuse_category")] if p
                )
                db.add(AnalysisResult(
                    call_id=call_id,
                    summary=summary,
                    key_segments=fields,
                    followup_suggestion=fields.get("promise_date"),
                    prompt_version="v1",
                    llm_model=llm_result.get("model"),
                    needs_review=bool(llm_result.get("needs_review", False)),
                ))
                call.result_tag = fields.get("intent")

            call.status = "processed"

    except Exception as exc:
        with suppress(Exception):
            with _get_db() as err_db:
                err_call = err_db.get(CallRecord, call_id)
                if err_call:
                    err_call.status = "failed"
        raise self.retry(exc=exc)

    finally:
        if tmp_path:
            with suppress(OSError):
                os.unlink(tmp_path)
```

- [ ] **Step 4: Run pipeline tests — confirm they pass**

```
/opt/homebrew/bin/pytest tests/worker/test_process_call.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Run full test suite — confirm no regressions**

```
/opt/homebrew/bin/pytest --tb=short -q
```

Expected: all tests pass (including `test_calls_v1.py` which has autouse mock protecting the upload endpoint from triggering the real pipeline)

- [ ] **Step 6: Commit**

```bash
git add poc/backend/app/worker/tasks/call_pipeline.py \
        poc/backend/tests/worker/test_process_call.py
git commit -m "feat: expand process_call pipeline — ASR + Transcript + LLM + AnalysisResult"
```

---

## Task 3: Call Schemas + `GET /calls/{call_id}` Fill Transcript/Analysis

**Files:**
- Modify: `poc/backend/app/schemas/call.py`
- Modify: `poc/backend/app/api/calls_v1.py` (update `get_call_detail`)
- Create: `poc/backend/tests/api/test_calls_v1_detail.py`

- [ ] **Step 1: Write failing tests for filled call detail**

```python
# poc/backend/tests/api/test_calls_v1_detail.py
import pytest
from httpx import AsyncClient


@pytest.fixture
def seeded_processed_call(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from app.core.crypto import encrypt_phone
    from app.models.call import AnalysisResult, CallRecord, Transcript

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800005678"),
        status="processed",
        object_key="calls/test/processed.mp3",
    )
    db_session.add(call)
    db_session.flush()

    db_session.add(Transcript(
        call_id=call.id,
        full_text="[坐席] 您好。\n[业主] 知道了月底缴。",
        segments=[{"speaker": 0, "start_ms": 0, "end_ms": 3000, "text": "您好。"}],
        asr_model="mock",
    ))
    db_session.add(AnalysisResult(
        call_id=call.id,
        summary="承诺缴 · 经济困难",
        key_segments={
            "intent": "承诺缴",
            "promise_date": "2026-04-30",
            "excuse_category": "经济困难",
            "compliance_disclosed": True,
            "risk_keywords": [],
            "confidence": 0.85,
            "needs_review": False,
        },
        followup_suggestion="2026-04-30",
        prompt_version="v1",
        llm_model="mock",
        needs_review=False,
    ))
    db_session.flush()
    return call


@pytest.mark.asyncio
async def test_call_detail_with_transcript_and_analysis(
    client: AsyncClient, agent_auth_headers, seeded_processed_call
):
    resp = await client.get(
        f"/api/v1/calls/{seeded_processed_call.id}", headers=agent_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "processed"

    t = data["transcript"]
    assert t is not None
    assert "您好" in t["full_text"]
    assert len(t["segments"]) == 1
    assert t["asr_model"] == "mock"

    a = data["analysis"]
    assert a is not None
    assert a["intent"] == "承诺缴"
    assert a["confidence"] == 0.85
    assert a["promise_date"] == "2026-04-30"
    assert a["needs_review"] is False


@pytest.mark.asyncio
async def test_call_detail_no_transcript_returns_null(
    client: AsyncClient, agent_auth_headers, seeded_member_user, seeded_tenant, seeded_case, db_session
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800009999"),
        status="uploaded",
    )
    db_session.add(call)
    db_session.flush()

    resp = await client.get(f"/api/v1/calls/{call.id}", headers=agent_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"] is None
    assert data["analysis"] is None
```

- [ ] **Step 2: Run tests — confirm they fail**

```
/opt/homebrew/bin/pytest tests/api/test_calls_v1_detail.py -v
```

Expected: FAIL (schemas don't have `TranscriptOut`/`AnalysisResultOut` yet; `get_call_detail` returns hardcoded `None`)

- [ ] **Step 3: Update schemas in `poc/backend/app/schemas/call.py`**

Replace the `CallDetailResponse` section (from `# ── Sprint 3a` to end of file) with:

```python
# ── Sprint 3a: calls_v1 schemas ───────────────────────────────


class CallUploadResponse(BaseModel):
    call_id: int
    status: str


class CallListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: Optional[int]
    callee_phone_masked: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_sec: Optional[int]
    status: str
    created_at: datetime


# ── Sprint 3b: transcript + analysis schemas ──────────────────


class TranscriptSegment(BaseModel):
    speaker: int
    start_ms: int
    end_ms: int
    text: str


class TranscriptOut(BaseModel):
    full_text: str
    segments: Optional[list[TranscriptSegment]]
    asr_model: Optional[str]


class AnalysisResultOut(BaseModel):
    summary: Optional[str]
    intent: Optional[str]
    promise_date: Optional[str]
    excuse_category: Optional[str]
    compliance_disclosed: Optional[bool]
    risk_keywords: Optional[list[str]]
    confidence: Optional[float]
    needs_review: bool


class CallDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: Optional[int]
    callee_phone_masked: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_sec: Optional[int]
    recording_url: Optional[str]
    status: str
    transcript: Optional[TranscriptOut]
    analysis: Optional[AnalysisResultOut]
    created_at: datetime
```

- [ ] **Step 4: Update `get_call_detail` in `poc/backend/app/api/calls_v1.py`**

Add imports at the top of the file (with existing imports):

```python
from app.models.call import CallRecord, Transcript, AnalysisResult
from app.schemas.call import (
    CallDetailResponse, CallListItem, CallUploadResponse,
    TranscriptOut, TranscriptSegment, AnalysisResultOut,
)
```

Replace the `return CallDetailResponse(...)` block at the end of `get_call_detail` (currently returning `transcript=None, analysis=None`) with:

```python
    transcript_out: Optional[TranscriptOut] = None
    analysis_out: Optional[AnalysisResultOut] = None

    if call.status == "processed":
        t = db.execute(
            select(Transcript).where(Transcript.call_id == call_id)
        ).scalar_one_or_none()
        if t:
            segs = None
            if t.segments:
                segs = [TranscriptSegment(**s) for s in t.segments]
            transcript_out = TranscriptOut(
                full_text=t.full_text or "",
                segments=segs,
                asr_model=t.asr_model,
            )

        a = db.execute(
            select(AnalysisResult).where(AnalysisResult.call_id == call_id)
        ).scalar_one_or_none()
        if a:
            kv = a.key_segments or {}
            analysis_out = AnalysisResultOut(
                summary=a.summary,
                intent=kv.get("intent"),
                promise_date=kv.get("promise_date"),
                excuse_category=kv.get("excuse_category"),
                compliance_disclosed=kv.get("compliance_disclosed"),
                risk_keywords=kv.get("risk_keywords"),
                confidence=kv.get("confidence"),
                needs_review=a.needs_review,
            )

    return CallDetailResponse(
        id=call.id,
        case_id=call.case_id,
        callee_phone_masked=mask_phone(call.callee_phone_enc),
        started_at=call.started_at,
        ended_at=call.ended_at,
        duration_sec=call.duration_sec,
        recording_url=call.recording_url,
        status=call.status,
        transcript=transcript_out,
        analysis=analysis_out,
        created_at=call.created_at,
    )
```

- [ ] **Step 5: Run tests — confirm they pass**

```
/opt/homebrew/bin/pytest tests/api/test_calls_v1_detail.py tests/api/test_calls_v1.py -v
```

Expected: all pass (existing test `test_get_call_detail_returns_record` still passes: `transcript is None` for non-processed call)

- [ ] **Step 6: Run full suite**

```
/opt/homebrew/bin/pytest --tb=short -q
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add poc/backend/app/schemas/call.py \
        poc/backend/app/api/calls_v1.py \
        poc/backend/tests/api/test_calls_v1_detail.py
git commit -m "feat: fill transcript and analysis in GET /calls/{call_id}"
```

---

## Task 4: Admin Case Detail API (with call timeline)

**Files:**
- Modify: `poc/backend/app/schemas/case.py`
- Modify: `poc/backend/app/api/admin_cases.py`
- Create: `poc/backend/tests/api/test_admin_cases_detail.py`

> **No conflict:** existing `test_get_case_detail` in `test_admin_cases_list.py` only asserts `id` and `owner.name` — both present in new `CaseDetailResponse`.

- [ ] **Step 1: Write failing tests**

```python
# poc/backend/tests/api/test_admin_cases_detail.py
import pytest
from httpx import AsyncClient


@pytest.fixture
def seeded_processed_call_for_case(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from app.core.crypto import encrypt_phone
    from app.models.call import AnalysisResult, CallRecord, Transcript

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13811112222"),
        status="processed",
        duration_sec=222,
        result_tag="承诺缴",
    )
    db_session.add(call)
    db_session.flush()

    db_session.add(Transcript(
        call_id=call.id,
        full_text="业主称月底缴费。",
        asr_model="mock",
    ))
    db_session.add(AnalysisResult(
        call_id=call.id,
        summary="承诺缴 · 经济困难",
        key_segments={"intent": "承诺缴", "confidence": 0.87, "excuse_category": "经济困难"},
        needs_review=False,
    ))
    db_session.flush()
    return call


@pytest.mark.asyncio
async def test_admin_case_detail_includes_call_timeline(
    client: AsyncClient, admin_auth_headers, seeded_case, seeded_processed_call_for_case
):
    resp = await client.get(
        f"/api/v1/admin/cases/{seeded_case.id}", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == seeded_case.id
    assert "calls" in data
    assert "timeline_events" in data
    assert len(data["calls"]) == 1

    call_item = data["calls"][0]
    assert call_item["status"] == "processed"
    assert call_item["result_tag"] == "承诺缴"
    assert call_item["confidence"] == 0.87
    assert call_item["transcript_preview"] == "业主称月底缴费。"


@pytest.mark.asyncio
async def test_admin_case_detail_no_calls_returns_empty_list(
    client: AsyncClient, admin_auth_headers, seeded_case
):
    resp = await client.get(
        f"/api/v1/admin/cases/{seeded_case.id}", headers=admin_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["calls"] == []
    assert data["timeline_events"] == []
```

- [ ] **Step 2: Run tests — confirm they fail**

```
/opt/homebrew/bin/pytest tests/api/test_admin_cases_detail.py -v
```

Expected: FAIL (`calls` key not in response)

- [ ] **Step 3: Add schemas to `poc/backend/app/schemas/case.py`**

Add these classes at the end of the file (after `CaseAssignResponse`):

```python
# ── Sprint 3b: case detail with call timeline ──────────────────


class CaseCallItem(BaseModel):
    id: int
    started_at: Optional[datetime]
    duration_sec: Optional[int]
    status: str
    transcript_preview: Optional[str]
    result_tag: Optional[str]
    confidence: Optional[float]
    agent_name: Optional[str]


class TimelineEvent(BaseModel):
    type: str
    ts: datetime
    actor: Optional[str]
    note: Optional[str]


class CaseDetailResponse(BaseModel):
    id: int
    tenant_id: int
    project_id: Optional[int]
    owner: OwnerInfo
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
    calls: list[CaseCallItem]
    timeline_events: list[TimelineEvent]
```

Also add `phone: Optional[str] = None` field to `OwnerInfo` (for agent_internal role in Task 5):

```python
class OwnerInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: Optional[str] = None        # decrypted, only for agent_internal
    phone_masked: str
    building: Optional[str]
    room: Optional[str]
    do_not_call: bool
```

- [ ] **Step 4: Update `admin_cases.py` — change `get_case` to return `CaseDetailResponse`**

Add imports at top of `poc/backend/app/api/admin_cases.py`:

```python
from sqlalchemy import func, select, update
from app.models.call import AnalysisResult, CallRecord, Transcript
from app.models.user import UserAccount
from app.schemas.case import (
    CaseAssignRequest, CaseAssignResponse, CaseCallItem, CaseDetailResponse,
    CaseImportRequest, CaseImportResponse, CaseResponse, CaseStageUpdate,
    CaseWithOwnerResponse, OwnerInfo, TimelineEvent,
)
```

Replace the existing `get_case` function (currently `GET /cases/{case_id}` with `response_model=CaseWithOwnerResponse`):

```python
@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
async def get_case(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[UserAccount, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseDetailResponse:
    tenant_id = _require_tenant(payload)
    row = db.execute(
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(
            CollectionCase.id == case_id,
            CollectionCase.tenant_id == tenant_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    case, owner = row[0], row[1]

    # Build call timeline
    call_rows = db.execute(
        select(CallRecord, UserAccount.name.label("agent_name"))
        .join(UserAccount, UserAccount.id == CallRecord.caller_user_id)
        .where(
            CallRecord.case_id == case_id,
            CallRecord.tenant_id == tenant_id,
        )
        .order_by(CallRecord.started_at.desc().nulls_last())
    ).all()

    call_items: list[CaseCallItem] = []
    for call_row in call_rows:
        call = call_row[0]
        agent_name = call_row[1]

        analysis = db.execute(
            select(AnalysisResult).where(AnalysisResult.call_id == call.id)
        ).scalar_one_or_none()
        transcript = db.execute(
            select(Transcript).where(Transcript.call_id == call.id)
        ).scalar_one_or_none()

        confidence = None
        if analysis and analysis.key_segments:
            confidence = analysis.key_segments.get("confidence")

        preview = None
        if transcript and transcript.full_text:
            preview = transcript.full_text[:100]

        call_items.append(CaseCallItem(
            id=call.id,
            started_at=call.started_at,
            duration_sec=call.duration_sec,
            status=call.status,
            transcript_preview=preview,
            result_tag=call.result_tag,
            confidence=confidence,
            agent_name=agent_name,
        ))

    return CaseDetailResponse(
        id=case.id,
        tenant_id=case.tenant_id,
        project_id=case.project_id,
        owner=OwnerInfo(
            id=owner.id,
            name=owner.name,
            phone_masked=mask_phone(owner.phone_enc),
            building=owner.building,
            room=owner.room,
            do_not_call=owner.do_not_call,
        ),
        assigned_to=case.assigned_to,
        pool_type=case.pool_type,
        stage=case.stage,
        amount_owed=case.amount_owed,
        months_overdue=case.months_overdue,
        priority_score=case.priority_score,
        last_contact_at=case.last_contact_at,
        monthly_contact_count=case.monthly_contact_count,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        calls=call_items,
        timeline_events=[],  # Sprint 4: add workorder/assignment events
    )
```

- [ ] **Step 5: Run tests — confirm new tests pass and no regressions**

```
/opt/homebrew/bin/pytest tests/api/test_admin_cases_detail.py tests/api/test_admin_cases_list.py -v
```

Expected: all pass (the old `test_get_case_detail` still passes since it checks `id` and `owner.name`)

- [ ] **Step 6: Run full suite**

```
/opt/homebrew/bin/pytest --tb=short -q
```

- [ ] **Step 7: Commit**

```bash
git add poc/backend/app/schemas/case.py \
        poc/backend/app/api/admin_cases.py \
        poc/backend/tests/api/test_admin_cases_detail.py
git commit -m "feat: admin GET /cases/{id} returns CaseDetailResponse with call timeline"
```

---

## Task 5: Agent Case Detail API

**Files:**
- Modify: `poc/backend/app/api/agent_cases.py`
- Create: `poc/backend/tests/api/test_agent_cases_detail.py`

- [ ] **Step 1: Write failing tests**

```python
# poc/backend/tests/api/test_agent_cases_detail.py
import pytest
from httpx import AsyncClient


@pytest.fixture
def agent_internal_auth_headers(seeded_member_user, seeded_tenant):
    from app.core.security import create_access_token
    token = create_access_token({
        "sub": str(seeded_member_user.id),
        "user_id": seeded_member_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "agent_internal",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def external_agent_user(db_session, seeded_tenant):
    from app.core.crypto import encrypt_phone
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    user = UserAccount(
        phone_enc=encrypt_phone("13700007777"),
        name="外包坐席老李",
        password_hash=get_password_hash("External@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserTenantMembership(
        user_id=user.id,
        tenant_id=seeded_tenant.id,
        role="agent_external",
        source_type="EXTERNAL",
        is_active=True,
    ))
    db_session.flush()
    return user


@pytest.fixture
def external_agent_headers(external_agent_user, seeded_tenant):
    from app.core.security import create_access_token
    token = create_access_token({
        "sub": str(external_agent_user.id),
        "user_id": external_agent_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "agent_external",
        "scope": f"tenant:{seeded_tenant.id}",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_agent_internal_gets_plain_phone(
    client: AsyncClient, agent_internal_auth_headers, seeded_case, seeded_owner
):
    resp = await client.get(
        f"/api/v1/agent/cases/{seeded_case.id}", headers=agent_internal_auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["owner"]["phone"] == "13712345678"   # decrypted
    assert "****" not in data["owner"]["phone"]


@pytest.mark.asyncio
async def test_agent_external_gets_masked_phone(
    client: AsyncClient, external_agent_headers, seeded_case,
    seeded_owner, db_session, seeded_tenant, external_agent_user
):
    # Assign case to external agent so they can see it
    from app.models.case import CollectionCase
    case = db_session.get(CollectionCase, seeded_case.id)
    case.assigned_to = external_agent_user.id
    case.pool_type = "private"
    db_session.flush()

    resp = await client.get(
        f"/api/v1/agent/cases/{seeded_case.id}", headers=external_agent_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["owner"]["phone"] is None
    assert "****" in data["owner"]["phone_masked"]


@pytest.mark.asyncio
async def test_agent_cannot_see_other_agents_case(
    client: AsyncClient, agent_internal_auth_headers, db_session,
    seeded_tenant, seeded_owner, external_agent_user
):
    from app.models.case import CollectionCase
    # Case assigned to external_agent_user (not seeded_member_user)
    case = CollectionCase(
        tenant_id=seeded_tenant.id,
        owner_id=seeded_owner.id,
        pool_type="private",
        stage="new",
        assigned_to=external_agent_user.id,
        priority_score=0,
    )
    db_session.add(case)
    db_session.flush()

    resp = await client.get(
        f"/api/v1/agent/cases/{case.id}", headers=agent_internal_auth_headers
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests — confirm they fail**

```
/opt/homebrew/bin/pytest tests/api/test_agent_cases_detail.py -v
```

Expected: FAIL (no `GET /agent/cases/{case_id}` endpoint)

- [ ] **Step 3: Add `GET /cases/{case_id}` to `agent_cases.py`**

Add imports at top of `poc/backend/app/api/agent_cases.py`:

```python
from app.core.crypto import decrypt_phone
from app.models.call import AnalysisResult, CallRecord, Transcript
from app.schemas.case import (
    CaseCallItem, CaseDetailResponse, CaseResponse,
    CaseWithOwnerResponse, OwnerInfo, TimelineEvent,
)
```

Add this endpoint to `poc/backend/app/api/agent_cases.py` (BEFORE the `claim` endpoint to avoid route shadowing):

```python
@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
async def get_case_detail(
    case_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    user: Annotated[UserAccount, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CaseDetailResponse:
    tenant_id = _require_tenant(payload)
    role: str = payload.get("role", "")

    row = db.execute(
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(
            CollectionCase.id == case_id,
            CollectionCase.tenant_id == tenant_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在"},
        )
    case, owner = row[0], row[1]

    # Agent can only see cases assigned to them OR public-pool cases
    if case.assigned_to != user.id and not (
        case.pool_type == "public" and case.assigned_to is None
    ):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "无权访问此案件"},
        )

    # Phone visibility by role
    phone_plain = decrypt_phone(owner.phone_enc) if role == "agent_internal" else None

    # Build call items (same helper logic as admin_cases)
    from app.models.user import UserAccount as UA
    call_rows = db.execute(
        select(CallRecord, UA.name.label("agent_name"))
        .join(UA, UA.id == CallRecord.caller_user_id)
        .where(CallRecord.case_id == case_id, CallRecord.tenant_id == tenant_id)
        .order_by(CallRecord.started_at.desc().nulls_last())
    ).all()

    call_items: list[CaseCallItem] = []
    for call_row in call_rows:
        call = call_row[0]
        agent_name = call_row[1]
        analysis = db.execute(
            select(AnalysisResult).where(AnalysisResult.call_id == call.id)
        ).scalar_one_or_none()
        transcript = db.execute(
            select(Transcript).where(Transcript.call_id == call.id)
        ).scalar_one_or_none()
        confidence = None
        if analysis and analysis.key_segments:
            confidence = analysis.key_segments.get("confidence")
        preview = transcript.full_text[:100] if transcript and transcript.full_text else None
        call_items.append(CaseCallItem(
            id=call.id,
            started_at=call.started_at,
            duration_sec=call.duration_sec,
            status=call.status,
            transcript_preview=preview,
            result_tag=call.result_tag,
            confidence=confidence,
            agent_name=agent_name,
        ))

    from app.core.security import mask_phone
    return CaseDetailResponse(
        id=case.id,
        tenant_id=case.tenant_id,
        project_id=case.project_id,
        owner=OwnerInfo(
            id=owner.id,
            name=owner.name,
            phone=phone_plain,
            phone_masked=mask_phone(owner.phone_enc),
            building=owner.building,
            room=owner.room,
            do_not_call=owner.do_not_call,
        ),
        assigned_to=case.assigned_to,
        pool_type=case.pool_type,
        stage=case.stage,
        amount_owed=case.amount_owed,
        months_overdue=case.months_overdue,
        priority_score=case.priority_score,
        last_contact_at=case.last_contact_at,
        monthly_contact_count=case.monthly_contact_count,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        calls=call_items,
        timeline_events=[],
    )
```

- [ ] **Step 4: Run tests — confirm pass**

```
/opt/homebrew/bin/pytest tests/api/test_agent_cases_detail.py tests/api/test_agent_cases.py -v
```

Expected: all pass

- [ ] **Step 5: Run full suite**

```
/opt/homebrew/bin/pytest --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add poc/backend/app/api/agent_cases.py \
        poc/backend/tests/api/test_agent_cases_detail.py
git commit -m "feat: agent GET /cases/{id} with role-based phone visibility"
```

---

## Task 6: Admin Case Detail Frontend Page

**Files:**
- Create: `frontend/src/pages/admin/cases/detail.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/pages/admin/cases/detail.tsx
import { useGo, useOne } from "@refinedev/core";
import { ArrowLeft, Phone, PhoneOff } from "lucide-react";
import { useParams } from "react-router-dom";
import type { CaseDetailResponse } from "../../../types/case";

const STAGE_LABELS: Record<string, string> = {
  new: "待处理", in_progress: "处理中", promised: "已承诺",
  paid: "已缴费", escalated: "已上报", closed: "已关闭",
};

const RESULT_TAG_COLORS: Record<string, React.CSSProperties> = {
  "承诺缴": { background: "var(--color-warning-light)", color: "var(--color-warning)" },
  "立即缴": { background: "var(--color-success-light)", color: "var(--color-success)" },
  "推托": { background: "var(--color-neutral-100)", color: "var(--color-neutral-600)" },
  "拒缴": { background: "var(--color-danger-light)", color: "var(--color-danger)" },
};

export function AdminCaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();

  const { data, isLoading } = useOne<CaseDetailResponse>({
    resource: "admin/cases",
    id: id!,
  });

  const detail = data?.data;

  if (isLoading) {
    return <div className="text-sm text-[var(--color-neutral-400)] p-8">加载中…</div>;
  }
  if (!detail) {
    return <div className="text-sm text-[var(--color-danger)] p-8">案件不存在</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => go({ to: "/admin/cases" })}
          className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          案件详情
        </h1>
        <span
          className="inline-flex px-2 py-0.5 text-xs rounded-full font-medium"
          style={{ background: "var(--color-primary-light)", color: "var(--color-primary)" }}
        >
          {STAGE_LABELS[detail.stage] ?? detail.stage}
        </span>
      </div>

      <div className="grid gap-6" style={{ gridTemplateColumns: "340px 1fr" }}>
        {/* Left column */}
        <div className="space-y-4">
          <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
            <div className="flex items-center gap-3 mb-4">
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center text-xl font-bold"
                style={{ background: "var(--color-primary-light)", color: "var(--color-primary)" }}
              >
                {detail.owner.name[0]}
              </div>
              <div>
                <div className="text-base font-semibold">{detail.owner.name}</div>
                <div className="text-xs text-[var(--color-neutral-500)]">
                  {[detail.owner.building, detail.owner.room].filter(Boolean).join(" ")}
                </div>
              </div>
            </div>
            <div className="text-sm text-[var(--color-neutral-600)] mb-4">
              {detail.owner.phone_masked}
            </div>
            {detail.amount_owed && (
              <div
                className="rounded-lg p-4 text-center mb-4"
                style={{ background: "var(--color-danger-light)" }}
              >
                <div className="text-xs text-[var(--color-neutral-400)] mb-1">累计欠费</div>
                <div className="text-3xl font-bold" style={{ color: "var(--color-danger)" }}>
                  ¥{Number(detail.amount_owed).toLocaleString()}
                </div>
                <div className="text-xs text-[var(--color-neutral-500)]">
                  共 {detail.months_overdue} 个月
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right column — timeline */}
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
          <h2 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-4">
            通话记录
          </h2>
          {detail.calls.length === 0 ? (
            <div className="text-sm text-[var(--color-neutral-400)]">暂无通话记录</div>
          ) : (
            <div className="space-y-4">
              {detail.calls.map((call) => (
                <div
                  key={call.id}
                  className="border border-[var(--color-neutral-100)] rounded-lg p-4"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {call.status === "processed" ? (
                        <Phone className="w-4 h-4 text-[var(--color-success)]" />
                      ) : (
                        <PhoneOff className="w-4 h-4 text-[var(--color-neutral-400)]" />
                      )}
                      <span className="text-sm font-medium">
                        {call.duration_sec
                          ? `${Math.floor(call.duration_sec / 60)}分${call.duration_sec % 60}秒`
                          : "—"}
                      </span>
                    </div>
                    <span className="text-xs text-[var(--color-neutral-400)]">
                      {call.started_at
                        ? new Date(call.started_at).toLocaleString("zh-CN")
                        : "—"}{" "}
                      · {call.agent_name}
                    </span>
                  </div>
                  {call.transcript_preview && (
                    <div
                      className="rounded p-3 text-sm mb-2"
                      style={{ background: "var(--color-neutral-50)" }}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-medium text-[var(--color-neutral-600)]">
                          AI 摘要
                        </span>
                        {call.result_tag && (
                          <span
                            className="inline-flex px-1.5 py-0.5 text-xs rounded font-medium"
                            style={RESULT_TAG_COLORS[call.result_tag] ?? {}}
                          >
                            {call.result_tag}
                          </span>
                        )}
                        {call.confidence != null && (
                          <span className="text-xs text-[var(--color-neutral-400)]">
                            置信度 {call.confidence.toFixed(2)}
                          </span>
                        )}
                      </div>
                      <p className="text-[var(--color-neutral-700)] text-xs">
                        {call.transcript_preview}
                      </p>
                      <div className="flex gap-3 mt-2">
                        <button
                          type="button"
                          onClick={() => go({ to: `/calls/${call.id}` })}
                          className="text-xs text-[var(--color-primary)] hover:underline"
                        >
                          完整 AI 分析
                        </button>
                      </div>
                    </div>
                  )}
                  {call.status !== "processed" && (
                    <div className="text-xs text-[var(--color-neutral-400)]">
                      状态: {call.status}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add `CaseDetailResponse` type to frontend types**

Create `frontend/src/types/case.ts`:

```ts
export interface CaseCallItem {
  id: number;
  started_at: string | null;
  duration_sec: number | null;
  status: string;
  transcript_preview: string | null;
  result_tag: string | null;
  confidence: number | null;
  agent_name: string | null;
}

export interface TimelineEvent {
  type: string;
  ts: string;
  actor: string | null;
  note: string | null;
}

export interface OwnerInfo {
  id: number;
  name: string;
  phone: string | null;
  phone_masked: string;
  building: string | null;
  room: string | null;
  do_not_call: boolean;
}

export interface CaseDetailResponse {
  id: number;
  tenant_id: number;
  project_id: number | null;
  owner: OwnerInfo;
  assigned_to: number | null;
  pool_type: string;
  stage: string;
  amount_owed: string | null;
  months_overdue: number | null;
  priority_score: number;
  last_contact_at: string | null;
  monthly_contact_count: number;
  status: string;
  created_at: string;
  updated_at: string;
  calls: CaseCallItem[];
  timeline_events: TimelineEvent[];
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/admin/cases/detail.tsx frontend/src/types/case.ts
git commit -m "feat: admin case detail page with call timeline"
```

---

## Task 7: Call Detail Frontend Page

**Files:**
- Create: `frontend/src/pages/calls/detail.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/pages/calls/detail.tsx
import { useGo, useOne } from "@refinedev/core";
import { ArrowLeft, Mic } from "lucide-react";
import { useParams } from "react-router-dom";

interface TranscriptSegment {
  speaker: number;
  start_ms: number;
  end_ms: number;
  text: string;
}

interface TranscriptData {
  full_text: string;
  segments: TranscriptSegment[] | null;
  asr_model: string | null;
}

interface AnalysisData {
  summary: string | null;
  intent: string | null;
  promise_date: string | null;
  excuse_category: string | null;
  compliance_disclosed: boolean | null;
  risk_keywords: string[] | null;
  confidence: number | null;
  needs_review: boolean;
}

interface CallDetailData {
  id: number;
  case_id: number | null;
  callee_phone_masked: string;
  started_at: string | null;
  ended_at: string | null;
  duration_sec: number | null;
  recording_url: string | null;
  status: string;
  transcript: TranscriptData | null;
  analysis: AnalysisData | null;
  created_at: string;
}

export function CallDetailPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();

  const { data, isLoading } = useOne<CallDetailData>({
    resource: "calls",
    id: id!,
  });

  const detail = data?.data;

  if (isLoading) {
    return <div className="text-sm text-[var(--color-neutral-400)] p-8">加载中…</div>;
  }
  if (!detail) {
    return <div className="text-sm text-[var(--color-danger)] p-8">通话记录不存在</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => go({ to: -1 as unknown as string })}
          className="text-[var(--color-neutral-400)] hover:text-[var(--color-neutral-700)]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <Mic className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold text-[var(--color-neutral-900)]">
          通话详情
        </h1>
        <span className="text-sm text-[var(--color-neutral-400)]">
          {detail.started_at ? new Date(detail.started_at).toLocaleString("zh-CN") : "—"}
          {detail.duration_sec
            ? `  ·  ${Math.floor(detail.duration_sec / 60)}分${detail.duration_sec % 60}秒`
            : ""}
        </span>
      </div>

      {/* Recording player */}
      {detail.recording_url && (
        <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-4 mb-4">
          <div className="text-xs font-medium text-[var(--color-neutral-600)] mb-2">录音播放</div>
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <audio controls src={detail.recording_url} className="w-full" />
        </div>
      )}

      {detail.status !== "processed" && (
        <div
          className="rounded-lg p-4 mb-4 text-sm"
          style={{ background: "var(--color-neutral-50)", color: "var(--color-neutral-500)" }}
        >
          通话正在处理中（{detail.status}），转写和分析结果即将生成…
        </div>
      )}

      {detail.status === "processed" && (
        <div className="grid gap-4" style={{ gridTemplateColumns: "1fr 340px" }}>
          {/* Transcript */}
          <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
            <h2 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-4">
              通话转写
            </h2>
            {detail.transcript ? (
              <div className="space-y-2">
                {detail.transcript.segments ? (
                  detail.transcript.segments.map((seg, i) => (
                    <div key={i} className="flex gap-3 text-sm">
                      <span
                        className="shrink-0 font-medium w-12"
                        style={{
                          color: seg.speaker === 0
                            ? "var(--color-primary)"
                            : "var(--color-neutral-700)",
                        }}
                      >
                        {seg.speaker === 0 ? "坐席" : "业主"}
                      </span>
                      <span className="text-[var(--color-neutral-700)]">{seg.text}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-[var(--color-neutral-700)] whitespace-pre-wrap">
                    {detail.transcript.full_text}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-sm text-[var(--color-neutral-400)]">暂无转写内容</p>
            )}
          </div>

          {/* Analysis */}
          <div className="bg-white border border-[var(--color-neutral-200)] rounded-lg p-5">
            <h2 className="text-sm font-semibold text-[var(--color-neutral-900)] mb-4">
              AI 分析
            </h2>
            {detail.analysis ? (
              <div className="space-y-3 text-sm">
                {detail.analysis.summary && (
                  <div>
                    <div className="text-xs text-[var(--color-neutral-500)] mb-1">摘要</div>
                    <p className="text-[var(--color-neutral-800)]">{detail.analysis.summary}</p>
                  </div>
                )}
                {detail.analysis.intent && (
                  <div className="flex justify-between">
                    <span className="text-[var(--color-neutral-500)]">意图</span>
                    <span className="font-medium">{detail.analysis.intent}</span>
                  </div>
                )}
                {detail.analysis.promise_date && (
                  <div className="flex justify-between">
                    <span className="text-[var(--color-neutral-500)]">承诺缴费日期</span>
                    <span className="font-medium">{detail.analysis.promise_date}</span>
                  </div>
                )}
                {detail.analysis.excuse_category && (
                  <div className="flex justify-between">
                    <span className="text-[var(--color-neutral-500)]">推托类型</span>
                    <span>{detail.analysis.excuse_category}</span>
                  </div>
                )}
                {detail.analysis.confidence != null && (
                  <div className="flex justify-between">
                    <span className="text-[var(--color-neutral-500)]">置信度</span>
                    <span>{(detail.analysis.confidence * 100).toFixed(0)}%</span>
                  </div>
                )}
                {detail.analysis.risk_keywords && detail.analysis.risk_keywords.length > 0 && (
                  <div>
                    <div className="text-xs text-[var(--color-neutral-500)] mb-1">风险词</div>
                    <div className="flex flex-wrap gap-1">
                      {detail.analysis.risk_keywords.map((kw) => (
                        <span
                          key={kw}
                          className="inline-flex px-2 py-0.5 text-xs rounded"
                          style={{
                            background: "var(--color-danger-light)",
                            color: "var(--color-danger)",
                          }}
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {detail.analysis.needs_review && (
                  <div
                    className="rounded p-2 text-xs"
                    style={{
                      background: "var(--color-warning-light)",
                      color: "var(--color-warning)",
                    }}
                  >
                    ⚠️ 需要人工复核
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-[var(--color-neutral-400)]">暂无分析结果</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/calls/detail.tsx
git commit -m "feat: call detail page with transcript and analysis"
```

---

## Task 8: Agent Workstation Frontend Page

**Files:**
- Create: `frontend/src/pages/agent/cases/detail.tsx`

- [ ] **Step 1: Create the 4-column workstation component**

```tsx
// frontend/src/pages/agent/cases/detail.tsx
import { useGo, useList, useOne } from "@refinedev/core";
import { useState } from "react";
import { useParams } from "react-router-dom";
import type { CaseDetailResponse } from "../../../types/case";
import type { PaginatedResponse } from "../../../types";

export function AgentWorkstationPage() {
  const { id } = useParams<{ id: string }>();
  const go = useGo();
  const [selectedCallIdx, setSelectedCallIdx] = useState(0);

  const { data: listData } = useList<CaseDetailResponse>({
    resource: "agent/cases",
    pagination: { currentPage: 1, pageSize: 50 },
  });

  const cases: CaseDetailResponse[] =
    (listData?.data as unknown as PaginatedResponse<CaseDetailResponse>)?.items ??
    (listData?.data as CaseDetailResponse[] | undefined) ??
    [];

  const { data: detailData, isLoading } = useOne<CaseDetailResponse>({
    resource: "agent/cases",
    id: id!,
  });

  const detail = detailData?.data;
  const selectedCall = detail?.calls[selectedCallIdx] ?? null;

  return (
    <div
      className="h-[calc(100vh-64px)] overflow-hidden"
      style={{ display: "grid", gridTemplateColumns: "280px 240px 1fr 340px" }}
    >
      {/* col-cases */}
      <div className="border-r border-[var(--color-neutral-200)] flex flex-col overflow-hidden">
        <div className="p-3 border-b border-[var(--color-neutral-200)]">
          <span className="text-sm font-semibold text-[var(--color-neutral-900)]">我的案件</span>
        </div>
        <div className="overflow-y-auto flex-1">
          {cases.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => go({ to: `/agent/cases/${c.id}` })}
              className={`w-full text-left px-3 py-3 border-b border-[var(--color-neutral-100)] text-sm hover:bg-[var(--color-neutral-50)] ${
                String(c.id) === id ? "border-l-2 border-l-[var(--color-primary)] bg-blue-50" : ""
              }`}
            >
              <div className="font-medium text-[var(--color-neutral-900)]">{c.owner.name}</div>
              <div className="text-xs text-[var(--color-neutral-400)] mt-0.5">
                {c.owner.building} {c.owner.room}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* col-profile */}
      <div className="border-r border-[var(--color-neutral-200)] flex flex-col overflow-y-auto p-4">
        {isLoading && <div className="text-sm text-[var(--color-neutral-400)]">加载中…</div>}
        {detail && (
          <>
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center text-xl font-bold mb-3"
              style={{ background: "var(--color-primary-light)", color: "var(--color-primary)" }}
            >
              {detail.owner.name[0]}
            </div>
            <div className="text-sm font-semibold mb-1">{detail.owner.name}</div>
            <div className="text-xs text-[var(--color-neutral-500)] mb-3">
              {[detail.owner.building, detail.owner.room].filter(Boolean).join(" ")}
            </div>
            {detail.owner.phone && (
              <div className="text-sm font-mono text-[var(--color-primary)] mb-1">
                {detail.owner.phone}
              </div>
            )}
            <div className="text-xs text-[var(--color-neutral-400)] mb-4">
              {detail.owner.phone_masked}
            </div>
            {detail.amount_owed && (
              <div
                className="rounded p-3 text-center mb-4"
                style={{ background: "var(--color-danger-light)" }}
              >
                <div className="text-xs text-[var(--color-neutral-400)]">欠费</div>
                <div
                  className="text-xl font-bold"
                  style={{ color: "var(--color-danger)" }}
                >
                  ¥{Number(detail.amount_owed).toLocaleString()}
                </div>
                <div className="text-xs text-[var(--color-neutral-500)]">
                  {detail.months_overdue} 个月
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* col-transcript */}
      <div className="border-r border-[var(--color-neutral-200)] flex flex-col overflow-hidden">
        <div className="p-3 border-b border-[var(--color-neutral-200)] flex gap-2 overflow-x-auto">
          {detail?.calls.map((call, idx) => (
            <button
              key={call.id}
              type="button"
              onClick={() => setSelectedCallIdx(idx)}
              className={`shrink-0 px-3 py-1 text-xs rounded-full border ${
                idx === selectedCallIdx
                  ? "border-[var(--color-primary)] text-[var(--color-primary)] bg-[var(--color-primary-light)]"
                  : "border-[var(--color-neutral-200)] text-[var(--color-neutral-600)]"
              }`}
            >
              通话 {idx + 1}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {!selectedCall && (
            <div className="text-sm text-[var(--color-neutral-400)]">暂无通话记录</div>
          )}
          {selectedCall && selectedCall.status !== "processed" && (
            <div className="text-sm text-[var(--color-neutral-400)]">
              转写处理中（{selectedCall.status}）…
            </div>
          )}
          {selectedCall?.transcript_preview && (
            <p className="text-sm text-[var(--color-neutral-700)] whitespace-pre-wrap leading-relaxed">
              {selectedCall.transcript_preview}
            </p>
          )}
        </div>
      </div>

      {/* col-ai */}
      <div className="flex flex-col overflow-y-auto p-4">
        <div className="text-sm font-semibold text-[var(--color-neutral-900)] mb-4">AI 分析</div>
        {!selectedCall && (
          <div className="text-sm text-[var(--color-neutral-400)]">选择通话查看分析</div>
        )}
        {selectedCall && selectedCall.status === "processed" && (
          <div className="space-y-3 text-sm">
            {selectedCall.result_tag && (
              <div className="flex justify-between">
                <span className="text-[var(--color-neutral-500)]">意图</span>
                <span className="font-medium">{selectedCall.result_tag}</span>
              </div>
            )}
            {selectedCall.confidence != null && (
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-[var(--color-neutral-500)]">置信度</span>
                  <span>{(selectedCall.confidence * 100).toFixed(0)}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-[var(--color-neutral-100)]">
                  <div
                    className="h-1.5 rounded-full"
                    style={{
                      width: `${selectedCall.confidence * 100}%`,
                      background: "var(--color-primary)",
                    }}
                  />
                </div>
              </div>
            )}
            <button
              type="button"
              onClick={() => go({ to: `/calls/${selectedCall.id}` })}
              className="text-xs text-[var(--color-primary)] hover:underline"
            >
              查看完整 AI 分析 →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/agent/cases/detail.tsx
git commit -m "feat: agent workstation 4-column case detail page"
```

---

## Task 9: Frontend Routing + Nav

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/config/nav.ts`

- [ ] **Step 1: Update `App.tsx` — add routes and resources**

Replace the `resources` array and add new `Route` elements. Full updated `App.tsx`:

```tsx
import { Authenticated, Refine } from "@refinedev/core";
import routerBindings from "@refinedev/react-router";
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
} from "react-router-dom";

import { AppLayout } from "./components/layout/AppLayout";
import { LoginPage } from "./pages/login";
import { TenantListPage } from "./pages/ops/tenants/index";
import { TenantNewPage } from "./pages/ops/tenants/new";
import { TenantDetailPage } from "./pages/ops/tenants/[id]";
import { UserListPage } from "./pages/admin/users/index";
import { UserNewPage } from "./pages/admin/users/new";
import { CaseListPage } from "./pages/admin/cases/index";
import { CaseImportPage } from "./pages/admin/cases/import";
import { AdminCaseDetailPage } from "./pages/admin/cases/detail";
import { AgentCaseListPage } from "./pages/agent/cases/index";
import { AgentWorkstationPage } from "./pages/agent/cases/detail";
import { CallDetailPage } from "./pages/calls/detail";
import { authProvider } from "./providers/auth-provider";
import { dataProvider } from "./providers";

function App() {
  return (
    <BrowserRouter>
      <Refine
        dataProvider={dataProvider}
        authProvider={authProvider}
        routerProvider={routerBindings}
        resources={[
          {
            name: "ops/tenants",
            list: "/ops/tenants",
            create: "/ops/tenants/new",
            show: "/ops/tenants/:id",
          },
          {
            name: "admin/users",
            list: "/admin/users",
            create: "/admin/users/new",
          },
          {
            name: "admin/cases",
            list: "/admin/cases",
            create: "/admin/cases/import",
            show: "/admin/cases/:id",
          },
          {
            name: "agent/cases",
            list: "/agent/cases",
            show: "/agent/cases/:id",
          },
          {
            name: "calls",
            show: "/calls/:id",
          },
        ]}
        options={{ syncWithLocation: true, warnWhenUnsavedChanges: false }}
      >
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <Authenticated key="app" fallback={<Navigate to="/login" replace />}>
                <AppLayout>
                  <Outlet />
                </AppLayout>
              </Authenticated>
            }
          >
            <Route
              path="/"
              element={
                <div className="text-[var(--color-neutral-900)]">
                  <h1 className="text-2xl font-semibold mb-2">欢迎使用有证慧催</h1>
                  <p className="text-sm text-[var(--color-neutral-600)]">
                    各功能模块正在开发中。
                  </p>
                </div>
              }
            />
            <Route path="/ops/tenants" element={<TenantListPage />} />
            <Route path="/ops/tenants/new" element={<TenantNewPage />} />
            <Route path="/ops/tenants/:id" element={<TenantDetailPage />} />
            <Route path="/admin/users" element={<UserListPage />} />
            <Route path="/admin/users/new" element={<UserNewPage />} />
            <Route path="/admin/cases" element={<CaseListPage />} />
            <Route path="/admin/cases/import" element={<CaseImportPage />} />
            <Route path="/admin/cases/:id" element={<AdminCaseDetailPage />} />
            <Route path="/agent/cases" element={<AgentCaseListPage />} />
            <Route path="/agent/cases/:id" element={<AgentWorkstationPage />} />
            <Route path="/calls/:id" element={<CallDetailPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Refine>
    </BrowserRouter>
  );
}

export default App;
```

- [ ] **Step 2: Update `nav.ts` — add detail links**

Replace the `admin` and `agent_internal`/`agent_external` sections in `poc/backend/../frontend/src/config/nav.ts`:

```ts
  admin: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "用户管理", path: "/admin/users" },
        { label: "案件管理", path: "/admin/cases" },
        { label: "导入案件", path: "/admin/cases/import" },
      ],
    },
  ],
  supervisor: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "案件总览", path: "/supervisor/cases" },
      ],
    },
  ],
  agent_internal: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "我的案件", path: "/agent/cases" },
      ],
    },
  ],
  agent_external: [
    {
      items: [
        { label: "控制台", path: "/" },
        { label: "我的案件", path: "/agent/cases" },
      ],
    },
  ],
```

(No changes needed — detail pages are navigated from list pages, not from nav)

- [ ] **Step 3: TypeScript check + build**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx tsc --noEmit && npm run build
```

Expected: no errors, build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/config/nav.ts
git commit -m "feat: add routes for admin/agent case detail and call detail pages"
```

---

## Task 10: Android JWT Migration

**Files:**
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/Api.kt`
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/MainActivity.kt`
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/CallWatcherService.kt`

> Android has no CI integration — verify by code review and manual test. No automated tests for Android in this sprint.

- [ ] **Step 1: Update `Api.kt` — v1 endpoints + JWT interceptor + new data classes**

Replace the entire content of `Api.kt`:

```kotlin
package com.autoluyin.demo

import android.content.Context
import com.squareup.moshi.JsonClass
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import retrofit2.http.*
import java.io.File
import java.util.concurrent.TimeUnit

// ── Data classes ──────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class CaseItem(
    val id: Long,
    val stage: String,
    val amount_owed: String?,
    val months_overdue: Int?,
    val owner: OwnerInfo,
)

@JsonClass(generateAdapter = true)
data class OwnerInfo(
    val name: String,
    val phone: String?,       // non-null for agent_internal
    val phone_masked: String,
    val building: String?,
    val room: String?,
)

@JsonClass(generateAdapter = true)
data class CasesResponse(
    val items: List<CaseItem>,
    val total: Int,
)

@JsonClass(generateAdapter = true)
data class UploadResp(val call_id: Long, val status: String)

@JsonClass(generateAdapter = true)
data class SelfCheckReq(
    val device_id: String,
    val recording_dir_ok: Boolean,
    val recording_toggle_on: Boolean,
    val permissions_ok: Boolean,
)

@JsonClass(generateAdapter = true)
data class SelfCheckResp(val can_call: Boolean)

@JsonClass(generateAdapter = true)
data class LoginReq(val phone: String, val password: String)

@JsonClass(generateAdapter = true)
data class LoginResp(val access_token: String, val token_type: String)

// ── API interface ─────────────────────────────────────────────

interface BackendApi {
    @POST("/api/v1/auth/login")
    suspend fun login(@Body body: LoginReq): LoginResp

    @POST("/api/v1/devices/self-check")
    suspend fun selfCheck(@Body body: SelfCheckReq): SelfCheckResp

    @GET("/api/v1/devices/config")
    suspend fun deviceConfig(@Query("device_id") deviceId: String): Map<String, Any?>

    @GET("/api/v1/agent/cases")
    suspend fun myCases(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): CasesResponse

    @Multipart
    @POST("/api/v1/calls/upload")
    suspend fun uploadRecording(
        @Part("case_id") caseId: okhttp3.RequestBody,
        @Part("device_id") deviceId: okhttp3.RequestBody,
        @Part("callee_phone") calleePhone: okhttp3.RequestBody,
        @Part("started_at") startedAt: okhttp3.RequestBody,
        @Part("ended_at") endedAt: okhttp3.RequestBody,
        @Part("duration_sec") durationSec: okhttp3.RequestBody,
        @Part file: MultipartBody.Part,
    ): UploadResp
}

// ── Auth interceptor ──────────────────────────────────────────

class AuthInterceptor(private val ctx: Context) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = AppConfig.jwtToken(ctx)
        val request = if (token != null) {
            chain.request().newBuilder()
                .addHeader("Authorization", "Bearer $token")
                .build()
        } else {
            chain.request()
        }
        return chain.proceed(request)
    }
}

// ── ApiClient ─────────────────────────────────────────────────

object ApiClient {
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    @Volatile private var current: BackendApi? = null
    @Volatile private var currentBaseUrl: String? = null

    fun get(ctx: Context): BackendApi {
        val configured = AppConfig.backendUrl(ctx)
            ?: error("backend url not configured; let user set it first")
        val cached = current
        if (cached != null && configured == currentBaseUrl) return cached
        return synchronized(this) {
            val again = current
            if (again != null && configured == currentBaseUrl) again
            else {
                val http = OkHttpClient.Builder()
                    .connectTimeout(15, TimeUnit.SECONDS)
                    .readTimeout(60, TimeUnit.SECONDS)
                    .writeTimeout(120, TimeUnit.SECONDS)
                    .addInterceptor(AuthInterceptor(ctx))
                    .build()
                val built = Retrofit.Builder()
                    .baseUrl(if (configured.endsWith("/")) configured else "$configured/")
                    .client(http)
                    .addConverterFactory(MoshiConverterFactory.create(moshi))
                    .build()
                    .create(BackendApi::class.java)
                current = built
                currentBaseUrl = configured
                built
            }
        }
    }

    fun invalidate() {
        synchronized(this) { current = null; currentBaseUrl = null }
    }

    fun textPart(s: String) = s.toRequestBody("text/plain".toMediaType())

    fun filePart(name: String, file: File, mime: String): MultipartBody.Part =
        MultipartBody.Part.createFormData(name, file.name, file.asRequestBody(mime.toMediaType()))
}
```

- [ ] **Step 2: Add `jwtToken` / `saveJwtToken` to `AppConfig.kt`**

In `poc/android/app/src/main/java/com/autoluyin/demo/AppConfig.kt`, add these functions (alongside existing `backendUrl` / `saveBackendUrl`):

```kotlin
fun jwtToken(ctx: Context): String? =
    ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("jwt_token", null)

fun saveJwtToken(ctx: Context, token: String) {
    ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
        .putString("jwt_token", token).apply()
}

fun clearJwtToken(ctx: Context) {
    ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
        .remove("jwt_token").apply()
}
```

Where `PREFS` is the existing SharedPreferences name constant (check current `AppConfig.kt` for the exact name — likely `"autoluyin_prefs"`).

- [ ] **Step 3: Update `MainActivity.kt` — JWT login flow + case list**

Replace `loadTasks()` and `onCallClick()` to use new API. Key changes only (replace these methods):

```kotlin
private fun loadTasks() {
    lifecycleScope.launch {
        try {
            val resp = ApiClient.get(this@MainActivity).myCases()
            adapter.submitCases(resp.items)
        } catch (t: Throwable) {
            if (t.message?.contains("401") == true || t.message?.contains("403") == true) {
                AppConfig.clearJwtToken(this@MainActivity)
                ApiClient.invalidate()
                showLoginDialog()
            } else {
                toast("加载案件失败: ${t.message}")
            }
        }
    }
}

private fun onCallClick(c: CaseItem) {
    if (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE)
        != PackageManager.PERMISSION_GRANTED) {
        toast("请先授予拨打电话权限"); return
    }
    if (AppConfig.backendUrl(this) == null) {
        toast("请先配置后端地址"); showBackendUrlDialog(); return
    }
    val phone = c.owner.phone ?: c.owner.phone_masked
    CallWatcherService.start(this, c.id, phone)
    startActivity(Intent(Intent.ACTION_CALL, Uri.parse("tel:$phone")))
}

private fun showLoginDialog() {
    val phoneInput = EditText(this).apply { hint = "手机号" }
    val pwdInput = EditText(this).apply {
        hint = "密码"
        inputType = android.text.InputType.TYPE_CLASS_TEXT or
                android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD
    }
    val layout = android.widget.LinearLayout(this).apply {
        orientation = android.widget.LinearLayout.VERTICAL
        setPadding(48, 16, 48, 0)
        addView(phoneInput)
        addView(pwdInput)
    }
    AlertDialog.Builder(this)
        .setTitle("登录")
        .setView(layout)
        .setPositiveButton("登录") { _, _ ->
            val phone = phoneInput.text.toString().trim()
            val pwd = pwdInput.text.toString()
            lifecycleScope.launch {
                try {
                    val resp = ApiClient.get(this@MainActivity)
                        .login(LoginReq(phone = phone, password = pwd))
                    AppConfig.saveJwtToken(this@MainActivity, resp.access_token)
                    ApiClient.invalidate()  // rebuild client with new token
                    doSelfCheck()
                } catch (t: Throwable) {
                    toast("登录失败: ${t.message}")
                }
            }
        }
        .setNegativeButton("取消", null)
        .show()
}
```

Also update `ensureBackendUrlThen` to check JWT after URL is set:

```kotlin
private fun ensureBackendUrlThen(next: () -> Unit) {
    val url = AppConfig.backendUrl(this)
    if (url.isNullOrBlank()) {
        showBackendUrlDialog(onSaved = next)
    } else if (AppConfig.jwtToken(this) == null) {
        showLoginDialog()
    } else {
        renderHeader()
        next()
    }
}
```

Also update `TaskAdapter` to `CaseAdapter` — replace adapter type to use `CaseItem`:

```kotlin
// In MainActivity class, change:
private val adapter = CaseAdapter(::onCallClick)
// ...

class CaseAdapter(
    private val onCall: (CaseItem) -> Unit,
) : RecyclerView.Adapter<CaseAdapter.VH>() {
    private val items = mutableListOf<CaseItem>()
    fun submitCases(list: List<CaseItem>) {
        items.clear(); items.addAll(list); notifyDataSetChanged()
    }
    fun findById(id: Long) = items.firstOrNull { it.id == id }
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_task, parent, false)
        return VH(v)
    }
    override fun onBindViewHolder(h: VH, p: Int) = h.bind(items[p])
    override fun getItemCount() = items.size
    inner class VH(v: android.view.View) : RecyclerView.ViewHolder(v) {
        private val title: TextView = v.findViewById(R.id.title)
        private val sub: TextView = v.findViewById(R.id.sub)
        private val btn: android.widget.Button = v.findViewById(R.id.btnCall)
        fun bind(c: CaseItem) {
            title.text = "[催收] ${c.owner.name}（${c.owner.building ?: ""}${c.owner.room ?: ""}）"
            sub.text = "欠 ${c.amount_owed ?: "—"} / ${c.months_overdue ?: "—"}个月"
            val phone = c.owner.phone ?: c.owner.phone_masked
            btn.text = "呼叫 ${phone.take(3)}****${phone.takeLast(4)}"
            btn.setOnClickListener { onCall(c) }
        }
    }
}
```

- [ ] **Step 4: Update `CallWatcherService.kt` — use `case_id` instead of `task_id`**

Change `EXTRA_TASK_ID` to `EXTRA_CASE_ID`, update companion object and `start()`:

```kotlin
companion object {
    const val EXTRA_CASE_ID = "case_id"    // was EXTRA_TASK_ID
    const val EXTRA_CALLEE  = "callee_phone"
    const val EXTRA_RESUME  = "resume_scan"
    private const val NOTIF_ID = 1001
    private const val CHANNEL  = "autoluyin_call_watch"
    private const val TAG      = "CallWatcher"

    fun start(ctx: Context, caseId: Long, callee: String) {
        val i = Intent(ctx, CallWatcherService::class.java).apply {
            putExtra(EXTRA_CASE_ID, caseId)
            putExtra(EXTRA_CALLEE, callee)
        }
        ctx.startForegroundService(i)
    }
}
```

In `onStartCommand`, replace `EXTRA_TASK_ID` with `EXTRA_CASE_ID`:

```kotlin
val caseId = intent?.getLongExtra(EXTRA_CASE_ID, 0) ?: 0
val callee = intent?.getStringExtra(EXTRA_CALLEE).orEmpty()
saveState(caseId = caseId, callee = callee, startedAt = 0, endedAt = 0, observed = false)
```

In `matchAndUpload()`, replace `taskId` with `caseId` and use new upload API:

```kotlin
private suspend fun matchAndUpload() {
    val prefs  = getSharedPreferences(PhoneStateReceiver.PREFS, Context.MODE_PRIVATE)
    val caseId = prefs.getLong(PhoneStateReceiver.KEY_TASK_ID, 0)
    val callee = prefs.getString(PhoneStateReceiver.KEY_CALLEE, "").orEmpty()
    val startedAt = prefs.getLong(PhoneStateReceiver.KEY_STARTED, 0)
    val endedAt = prefs.getLong(PhoneStateReceiver.KEY_ENDED, System.currentTimeMillis())

    if (startedAt == 0L || callee.isEmpty()) {
        Log.w(TAG, "matchAndUpload: missing state"); updateNotif("状态丢失"); clearState(); stopSelfDelayed(); return
    }

    val timeoutMs = AppConfig.runtime.scanTimeoutSec * 1000L
    val deadline  = System.currentTimeMillis() + timeoutMs
    var hit: RecordingScanner.MatchResult? = null
    while (System.currentTimeMillis() < deadline) {
        hit = RecordingScanner.findRecording(RecordingScanner.MatchInput(callee, startedAt, endedAt))
        if (hit != null) break
        delay(1500)
    }
    if (hit == null) { updateNotif("未找到录音"); clearState(); stopSelfDelayed(); return }

    val durSec = ((endedAt - startedAt) / 1000).toInt().coerceAtLeast(1)
    try {
        val resp = ApiClient.get(this@CallWatcherService).uploadRecording(
            caseId      = ApiClient.textPart(caseId.toString()),
            deviceId    = ApiClient.textPart(DeviceId.get(this@CallWatcherService)),
            calleePhone = ApiClient.textPart(callee),
            startedAt   = ApiClient.textPart(iso(startedAt)),
            endedAt     = ApiClient.textPart(iso(endedAt)),
            durationSec = ApiClient.textPart(durSec.toString()),
            file        = ApiClient.filePart("file", hit.file, mimeOf(hit.file)),
        )
        Log.i(TAG, "uploaded call=${resp.call_id}")
        updateNotif("上传完成 #${resp.call_id}")
        sendBroadcast(Intent("com.autoluyin.demo.UPLOAD_DONE")
            .setPackage(packageName)
            .putExtra("call_id", resp.call_id)
            .putExtra("case_id", caseId))
    } catch (t: Throwable) {
        Log.e(TAG, "upload failed", t)
        updateNotif("上传失败：${t.message}")
    }
    clearState(); stopSelfDelayed()
}
```

Update `saveState` signature to use `caseId`:

```kotlin
private fun saveState(caseId: Long, callee: String, startedAt: Long, endedAt: Long, observed: Boolean) {
    getSharedPreferences(PhoneStateReceiver.PREFS, Context.MODE_PRIVATE).edit()
        .putLong(PhoneStateReceiver.KEY_TASK_ID, caseId)   // reuse existing KEY for SharedPrefs key
        .putString(PhoneStateReceiver.KEY_CALLEE, callee)
        .putLong(PhoneStateReceiver.KEY_STARTED, startedAt)
        .putLong(PhoneStateReceiver.KEY_ENDED, endedAt)
        .putBoolean(PhoneStateReceiver.KEY_OBSERVED, observed)
        .apply()
}
```

- [ ] **Step 5: Run full backend test suite — confirm nothing broken**

```
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/pytest --tb=short -q
```

Expected: all tests pass

- [ ] **Step 6: Run frontend build**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx tsc --noEmit && npm run build
```

Expected: no errors

- [ ] **Step 7: Commit**

```bash
git add poc/android/app/src/main/java/com/autoluyin/demo/Api.kt \
        poc/android/app/src/main/java/com/autoluyin/demo/MainActivity.kt \
        poc/android/app/src/main/java/com/autoluyin/demo/CallWatcherService.kt \
        poc/android/app/src/main/java/com/autoluyin/demo/AppConfig.kt
git commit -m "feat: Android migrates to /api/v1/ endpoints with JWT auth and case_id upload"
```

---

## Final Verification

After all 10 tasks complete, run:

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/pytest --tb=short -q
```

Expected: 100+ tests, all green.

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx tsc --noEmit && npm run build
```

Expected: clean build, no TypeScript errors.
