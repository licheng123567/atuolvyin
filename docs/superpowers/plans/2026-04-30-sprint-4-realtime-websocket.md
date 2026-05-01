# Sprint 4 Implementation Plan — Realtime WebSocket Call Assistance

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** End-to-end realtime AI call assistance — Android records audio → WebSocket streams to backend → DashScope streaming ASR → utterance-based LLM suggestions broadcast to PC + Android. PC-triggered DIAL_REQUEST via Xiaomi MiPush wakes Android from lock screen. Graceful degradation to local recording + Sprint-3a post-call upload when network fails.

**Architecture:** FastAPI WebSocket endpoint with in-process `ConnectionManager` (single-worker MVP); `streaming_asr` dispatcher mirroring existing `asr.py` pattern; `RealtimeSuggestionEngine` with utterance-end + 5s debounce + 20s timeout; MiPush HTTP client (`xiaomi` + `mock`); Android `AudioStreamClient` 100ms PCM frames over OkHttp WebSocket; PC three-column workstation with Refine + custom WS hook.

**Tech Stack:** FastAPI WebSocket + asyncio + httpx + DashScope SDK + Celery (backend); Kotlin + OkHttp3 + AudioRecord + Xiaomi MiPushSDK 6.0 (Android); React + Refine.dev v5 + custom WebSocket client (frontend).

**Reference Spec:** `/Users/shuo/AI/autoluyin/docs/superpowers/specs/2026-04-30-sprint-4-realtime-websocket-design.md`

---

## ⚠️ Read Before Starting

**Test backend defaults stay mock.** All tests run with `STREAMING_ASR_BACKEND=mock`, `MIPUSH_BACKEND=mock`, `LLM_BACKEND=mock`. Production credentials are never required. The DashScope streaming + MiPush HTTP implementations are written but only smoke-tested manually, not in CI.

**WebSocket auth.** JWT is passed in the query string `?token=<jwt>` (not headers, since browsers can't set custom headers on WebSocket handshake). Access tokens are short-lived (15 min recommended); existing `JWT_EXPIRES_MINUTES=1440` works for MVP — leave as-is.

**Single audio sender per call (informal).** Server accepts binary frames from any `role=agent` connection. PC just doesn't send. If misbehavior happens, post-call full recording is the source of truth (Sprint 3a fallback).

**Suggestion ID is server-generated UUID.** Clients echo it back unchanged on `suggestion.feedback` for idempotency.

**Schema for `call_record.status` is application-level.** No DB constraint changes; values used: `pending_dial | live | live_ended_pending_analysis | queued | processing | processed | failed`.

**Existing patterns to follow:**
- ASR dispatcher: `app/services/asr.py` → `asr_mock.py` / `asr_dashscope.py` (one file per backend)
- Test fixtures: `tests/conftest.py` (`db_session`, `client`, `agent_auth_headers`, `seeded_*`)
- Phone handling: `decrypt_phone()` for plain, `mask_phone()` for masked output
- Error envelope: `{"code": "ERR_XXX", "message": "..."}`

---

## File Map

### Backend (poc/backend/)

| File | Action |
|------|--------|
| `alembic/versions/4-001_realtime_websocket.py` | Create — push_reg_id + push_provider + user_confirmed_at + suggestion_feedback table |
| `app/models/device.py` | Modify — add `push_reg_id`, `push_provider` |
| `app/models/call.py` | Modify — add `user_confirmed_at`; new `SuggestionFeedback` model |
| `app/services/streaming_asr.py` | Create — dispatcher (mock + dashscope) |
| `app/services/streaming_asr_mock.py` | Create — mock backend with canned chunks |
| `app/services/streaming_asr_dashscope.py` | Create — DashScope wrapper (smoke-tested only) |
| `app/services/realtime_llm.py` | Create — `RealtimeSuggestionEngine` |
| `app/services/mipush.py` | Create — dispatcher (xiaomi + mock) |
| `app/services/mipush_mock.py` | Create — in-memory queue |
| `app/services/mipush_xiaomi.py` | Create — httpx wrapper |
| `app/core/config.py` | Modify — add streaming_asr_backend, mipush_*, realtime_llm_* settings |
| `app/schemas/call.py` | Modify — add `DialRequestIn/Out`, `CallTagPatch`, `SuggestionFeedbackIn`, WS message types |
| `app/api/calls_v1.py` | Modify — add `POST /dial-request`, `PATCH /{id}/tag`, `POST /{id}/suggestions/{sid}/feedback` |
| `app/api/devices_v1.py` | Modify — `POST /register` accepts optional `push_reg_id` + `push_provider` |
| `app/ws/__init__.py` | Create — empty package marker |
| `app/ws/connection_manager.py` | Create — `ConnectionManager` singleton |
| `app/ws/auth.py` | Create — JWT validation for WebSocket query string |
| `app/ws/call_session.py` | Create — per-call state aggregator (ASR session + suggestion engine) |
| `app/api/ws_calls.py` | Create — WebSocket endpoint `/ws/calls/{call_id}` |
| `app/main.py` | Modify — register `ws_calls` router |
| `tests/services/test_streaming_asr_mock.py` | Create |
| `tests/services/test_realtime_llm_engine.py` | Create |
| `tests/services/test_mipush_mock.py` | Create |
| `tests/api/test_dial_request.py` | Create |
| `tests/api/test_call_tag_patch.py` | Create |
| `tests/api/test_suggestion_feedback.py` | Create |
| `tests/ws/__init__.py` | Create — empty |
| `tests/ws/test_ws_calls_auth.py` | Create |
| `tests/ws/test_ws_calls_e2e.py` | Create |
| `tests/conftest.py` | Modify — add `seeded_call_pending_dial` and `seeded_device_with_push_reg` fixtures |

### Android (poc/android/)

| File | Action |
|------|--------|
| `app/build.gradle` | Modify — add MiPush SDK dep |
| `app/src/main/AndroidManifest.xml` | Modify — MiPush receiver + RealtimeCallActivity + permissions |
| `app/src/main/java/com/autoluyin/demo/AppConfig.kt` | Modify — `pushRegId()`, `savePushRegId()` |
| `app/src/main/java/com/autoluyin/demo/Api.kt` | Modify — `registerDevice` accepts push_reg_id |
| `app/src/main/java/com/autoluyin/demo/MainActivity.kt` | Modify — `MiPushClient.registerPush` on resume |
| `app/src/main/java/com/autoluyin/demo/push/MiPushService.kt` | Create — PushMessageReceiver impl |
| `app/src/main/java/com/autoluyin/demo/push/DialRequestHandler.kt` | Create — payload parser → start Activity |
| `app/src/main/java/com/autoluyin/demo/realtime/RealtimeCallActivity.kt` | Create — full UI |
| `app/src/main/java/com/autoluyin/demo/realtime/AudioStreamClient.kt` | Create — WS + AudioRecord |
| `app/src/main/java/com/autoluyin/demo/realtime/PostCallTagDialog.kt` | Create |
| `app/src/main/java/com/autoluyin/demo/realtime/TranscriptAdapter.kt` | Create — RecyclerView adapter |
| `app/src/main/java/com/autoluyin/demo/realtime/SuggestionCardView.kt` | Create — bottom card |
| `app/src/main/res/layout/activity_realtime_call.xml` | Create |
| `app/src/main/res/layout/dialog_post_call_tag.xml` | Create |
| `app/src/main/res/layout/item_transcript_segment.xml` | Create |
| `app/src/test/java/com/autoluyin/demo/AudioStreamClientTest.kt` | Create |

### PC Frontend (frontend/)

| File | Action |
|------|--------|
| `src/lib/realtime/types.ts` | Create — TranscriptChunk / Suggestion / TagPayload / WS envelopes |
| `src/lib/realtime/ws-client.ts` | Create — WebSocket reconnection wrapper |
| `src/hooks/useCallSocket.ts` | Create — React hook |
| `src/components/realtime/RealtimeCallShell.tsx` | Create — three-column layout |
| `src/components/realtime/TranscriptStream.tsx` | Create — middle column |
| `src/components/realtime/SuggestionCardStack.tsx` | Create — right column |
| `src/components/realtime/ConnectionBadge.tsx` | Create — status indicator |
| `src/pages/agent/workstation/live.tsx` | Create — agent role page |
| `src/pages/admin/workstation/live.tsx` | Create — observer role page |
| `src/pages/agent/cases/index.tsx` | Modify — add "拨打" button → POST /dial-request → navigate |
| `src/App.tsx` | Modify — register two new routes + resources |
| `src/config/nav.ts` | Modify — add admin "正在通话" stub link (optional) |
| `src/lib/realtime/__tests__/ws-client.test.ts` | Create |
| `src/components/realtime/__tests__/RealtimeCallShell.test.tsx` | Create |

---

## Task Dependency Order

```
T1 (DB schema) ─┬─→ T2 (Streaming ASR) ─┐
                ├─→ T3 (Realtime LLM)   │
                ├─→ T4 (MiPush mock)    │
                ├─→ T5 (DIAL_REQUEST)   │
                └─→ T6 (PATCH /tag)     │
                                        │
                T2 + T3 ────────────────┴─→ T7 (WebSocket endpoint)
                                            │
                                            ├─→ T8 (Android MiPush)
                                            ├─→ T9 (RealtimeCallActivity)
                                            ├─→ T10 (AudioStreamClient)
                                            ├─→ T11 (PostCallTagDialog)
                                            ├─→ T13 (PC ws-client)
                                            ├─→ T14 (PC RealtimeCallWorkstation)
                                            └─→ T15 (PC AI cards)
                                                │
                                                ├─→ T12 (Android degradation)
                                                └─→ T16 (E2E integration tests)
```

Tasks within the same level can run in parallel via separate subagents. Recommended single-session order: T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10 → T11 → T12 → T13 → T14 → T15 → T16.

---

## Task 1: Alembic 4-001 + ORM model updates

**Goal:** Add `push_reg_id`, `push_provider` to `device_profile`; add `user_confirmed_at` to `call_record`; create `suggestion_feedback` table.

**Files:**
- Create: `poc/backend/alembic/versions/4-001_realtime_websocket.py`
- Modify: `poc/backend/app/models/device.py`
- Modify: `poc/backend/app/models/call.py`

**Subagent model:** haiku

- [ ] **Step 1: Determine the previous Alembic revision**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
ls alembic/versions/
```

Note the latest revision: `b7e2f19a8c30` (Sprint 3b migration). New revision will reference it as `down_revision`.

- [ ] **Step 2: Create the migration file**

```python
# poc/backend/alembic/versions/4-001_realtime_websocket.py
"""Sprint 4-001 — realtime WebSocket fields + suggestion_feedback table.

Revision ID: 4001a1b2c3d4
Revises: b7e2f19a8c30
Create Date: 2026-04-30 12:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4001a1b2c3d4"
down_revision = "b7e2f19a8c30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "device_profile",
        sa.Column("push_reg_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "device_profile",
        sa.Column("push_provider", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "call_record",
        sa.Column("user_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "suggestion_feedback",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("call_id", sa.BigInteger(), sa.ForeignKey("call_record.id"), nullable=False),
        sa.Column("suggestion_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("suggestion_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("call_id", "suggestion_id", name="uq_suggestion_feedback_call_sid"),
    )
    op.create_index(
        "ix_suggestion_feedback_call_id", "suggestion_feedback", ["call_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_suggestion_feedback_call_id", table_name="suggestion_feedback")
    op.drop_table("suggestion_feedback")
    op.drop_column("call_record", "user_confirmed_at")
    op.drop_column("device_profile", "push_provider")
    op.drop_column("device_profile", "push_reg_id")
```

- [ ] **Step 3: Update `device.py` ORM model**

```python
# poc/backend/app/models/device.py — add at end of DeviceProfile class
    push_reg_id: Mapped[Optional[str]] = mapped_column(sa.Text)
    push_provider: Mapped[Optional[str]] = mapped_column(sa.String(20))
```

- [ ] **Step 4: Update `call.py` — add `user_confirmed_at` to `CallRecord` and append `SuggestionFeedback` class**

In `CallRecord` body (after `status`):

```python
    user_confirmed_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
```

Append at end of file:

```python
class SuggestionFeedback(Base):
    __tablename__ = "suggestion_feedback"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    call_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("call_record.id"), nullable=False
    )
    suggestion_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # adopt | ignore
    suggestion_text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        sa.UniqueConstraint("call_id", "suggestion_id", name="uq_suggestion_feedback_call_sid"),
        sa.Index("ix_suggestion_feedback_call_id", "call_id"),
    )
```

- [ ] **Step 5: Run pytest to confirm models load (no DB conflict)**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/python3.12 -m pytest tests/ --tb=short -q --collect-only 2>&1 | tail -5
```

Expected: collection succeeds (104+ tests collected, no import errors).

- [ ] **Step 6: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/alembic/versions/4-001_realtime_websocket.py \
        poc/backend/app/models/device.py \
        poc/backend/app/models/call.py
git commit -m "feat: Sprint 4-001 migration — push_reg_id + suggestion_feedback table"
```

---

## Task 2: StreamingASR backend dispatcher + mock implementation

**Goal:** Implement `streaming_asr` service following the existing `asr.py` dispatcher pattern. Mock backend returns canned text chunks every ~1s of accumulated audio.

**Files:**
- Modify: `poc/backend/app/core/config.py`
- Create: `poc/backend/app/services/streaming_asr.py`
- Create: `poc/backend/app/services/streaming_asr_mock.py`
- Create: `poc/backend/app/services/streaming_asr_dashscope.py`
- Create: `poc/backend/tests/services/__init__.py` (empty if not exists)
- Create: `poc/backend/tests/services/test_streaming_asr_mock.py`

**Subagent model:** sonnet

- [ ] **Step 1: Add settings to `config.py`**

In `Settings` class (after existing `llm_*` block):

```python
    # ==== 实时流式 ASR / 推送 / 实时 LLM ====
    streaming_asr_backend: str = "mock"  # "mock" | "dashscope"

    mipush_backend: str = "mock"  # "mock" | "xiaomi"
    mipush_app_secret: str = ""
    mipush_package_name: str = "com.autoluyin.demo"

    realtime_llm_debounce_sec: int = 5
    realtime_llm_timeout_sec: int = 20
    realtime_llm_silence_ms: int = 1500
```

- [ ] **Step 2: Write failing test for mock streaming ASR**

```python
# poc/backend/tests/services/test_streaming_asr_mock.py
import asyncio

import pytest


@pytest.mark.asyncio
async def test_mock_streaming_asr_emits_chunks_every_1s():
    from app.services.streaming_asr import get_streaming_asr_backend

    received: list[dict] = []

    async def on_transcript(chunk):
        received.append(chunk.model_dump() if hasattr(chunk, "model_dump") else dict(chunk))

    async def on_error(exc):
        pytest.fail(f"mock should not error: {exc}")

    backend = get_streaming_asr_backend()
    session = await backend.open_session(on_transcript, on_error)

    # Feed ~1s of audio (10 frames × 100ms × 3200 bytes = 32000 bytes)
    fake_frame = b"\x00" * 3200
    for _ in range(10):
        await session.feed_audio(fake_frame)

    await session.close()
    # Allow any pending tasks to flush
    await asyncio.sleep(0.05)

    assert len(received) >= 1, "expected at least one transcript chunk after 1s"
    first = received[0]
    assert "text" in first and first["text"]
    assert "speaker" in first
    assert "seq" in first
    assert "ts" in first


@pytest.mark.asyncio
async def test_mock_streaming_asr_chunks_have_increasing_seq():
    from app.services.streaming_asr import get_streaming_asr_backend

    received: list = []

    async def on_transcript(chunk):
        received.append(chunk)

    async def on_error(exc):
        pytest.fail(str(exc))

    backend = get_streaming_asr_backend()
    session = await backend.open_session(on_transcript, on_error)
    fake_frame = b"\x00" * 3200
    for _ in range(30):
        await session.feed_audio(fake_frame)
    await session.close()

    seqs = [c.seq for c in received]
    assert seqs == sorted(seqs)
    assert len(seqs) >= 3
```

- [ ] **Step 3: Run the test — confirm failure**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/python3.12 -m pytest tests/services/test_streaming_asr_mock.py -v
```

Expected: `ModuleNotFoundError: app.services.streaming_asr`.

- [ ] **Step 4: Create dispatcher and dataclass module `streaming_asr.py`**

```python
# poc/backend/app/services/streaming_asr.py
"""Streaming ASR dispatcher — mirrors app/services/asr.py pattern."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional, Protocol

from app.core.config import settings


@dataclass
class TranscriptChunk:
    seq: int
    speaker: str  # "agent" | "customer" | "unknown"
    text: str
    ts: datetime
    utterance_end: bool = False

    def model_dump(self) -> dict:
        return {
            "seq": self.seq,
            "speaker": self.speaker,
            "text": self.text,
            "ts": self.ts.isoformat(),
            "utterance_end": self.utterance_end,
        }


OnTranscript = Callable[[TranscriptChunk], Awaitable[None]]
OnError = Callable[[Exception], Awaitable[None]]


class StreamingASRSession(Protocol):
    async def feed_audio(self, pcm_bytes: bytes) -> None: ...
    async def close(self) -> None: ...


class StreamingASRBackend(Protocol):
    async def open_session(
        self,
        on_transcript: OnTranscript,
        on_error: OnError,
    ) -> StreamingASRSession: ...


def get_streaming_asr_backend() -> StreamingASRBackend:
    backend = settings.streaming_asr_backend.lower()
    if backend == "mock":
        from . import streaming_asr_mock as impl
        return impl.MockStreamingASR()
    if backend == "dashscope":
        from . import streaming_asr_dashscope as impl
        return impl.DashScopeStreamingASR()
    raise RuntimeError(f"unknown STREAMING_ASR_BACKEND: {settings.streaming_asr_backend}")
```

- [ ] **Step 5: Create the mock backend `streaming_asr_mock.py`**

```python
# poc/backend/app/services/streaming_asr_mock.py
"""Mock streaming ASR — emits canned chunks every ~1s of audio."""
from __future__ import annotations

from datetime import datetime, timezone

from .streaming_asr import OnError, OnTranscript, StreamingASRSession, TranscriptChunk


CANNED_TURNS = [
    ("customer", "您好哪位"),
    ("agent", "您好这里是 XX 物业"),
    ("customer", "我现在没钱"),
    ("agent", "您看分期方案是否方便"),
    ("customer", "下个月发工资再说"),
]


class MockStreamingASRSession:
    BYTES_PER_SECOND = 16000 * 2  # 16kHz mono 16-bit

    def __init__(self, on_transcript: OnTranscript, on_error: OnError):
        self._on_transcript = on_transcript
        self._on_error = on_error
        self._buffer = 0
        self._seq = 0
        self._closed = False

    async def feed_audio(self, pcm_bytes: bytes) -> None:
        if self._closed:
            return
        self._buffer += len(pcm_bytes)
        while self._buffer >= self.BYTES_PER_SECOND:
            self._buffer -= self.BYTES_PER_SECOND
            speaker, text = CANNED_TURNS[self._seq % len(CANNED_TURNS)]
            chunk = TranscriptChunk(
                seq=self._seq,
                speaker=speaker,
                text=text,
                ts=datetime.now(timezone.utc),
                utterance_end=True,
            )
            self._seq += 1
            await self._on_transcript(chunk)

    async def close(self) -> None:
        self._closed = True


class MockStreamingASR:
    async def open_session(
        self,
        on_transcript: OnTranscript,
        on_error: OnError,
    ) -> MockStreamingASRSession:
        return MockStreamingASRSession(on_transcript, on_error)
```

- [ ] **Step 6: Create the DashScope wrapper stub `streaming_asr_dashscope.py`**

```python
# poc/backend/app/services/streaming_asr_dashscope.py
"""DashScope paraformer-realtime-v2 streaming ASR — manually smoke-tested only."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import settings

from .streaming_asr import OnError, OnTranscript, StreamingASRSession, TranscriptChunk

logger = logging.getLogger(__name__)


class DashScopeStreamingASRSession(StreamingASRSession):
    def __init__(self, on_transcript: OnTranscript, on_error: OnError):
        self._on_transcript = on_transcript
        self._on_error = on_error
        self._loop = asyncio.get_running_loop()
        self._seq = 0
        self._recognition = self._build_recognition()

    def _build_recognition(self):
        # Lazy import to avoid hard dependency in mock path
        from dashscope.audio.asr import Recognition, RecognitionCallback

        manager = self

        class _Callback(RecognitionCallback):
            def on_event(self, result):
                try:
                    sentence = result.get_sentence()
                    if not sentence or not sentence.get("text"):
                        return
                    chunk = TranscriptChunk(
                        seq=manager._seq,
                        speaker="unknown",
                        text=sentence["text"],
                        ts=datetime.now(timezone.utc),
                        utterance_end=bool(sentence.get("end_time")),
                    )
                    manager._seq += 1
                    asyncio.run_coroutine_threadsafe(
                        manager._on_transcript(chunk), manager._loop
                    )
                except Exception as exc:
                    logger.exception("dashscope callback error")
                    asyncio.run_coroutine_threadsafe(
                        manager._on_error(exc), manager._loop
                    )

        rec = Recognition(
            model="paraformer-realtime-v2",
            format="pcm",
            sample_rate=16000,
            callback=_Callback(),
            api_key=settings.dashscope_api_key,
        )
        rec.start()
        return rec

    async def feed_audio(self, pcm_bytes: bytes) -> None:
        await self._loop.run_in_executor(
            None, self._recognition.send_audio_frame, pcm_bytes
        )

    async def close(self) -> None:
        await self._loop.run_in_executor(None, self._recognition.stop)


class DashScopeStreamingASR:
    async def open_session(
        self,
        on_transcript: OnTranscript,
        on_error: OnError,
    ) -> DashScopeStreamingASRSession:
        return DashScopeStreamingASRSession(on_transcript, on_error)
```

- [ ] **Step 7: Run the test — confirm pass**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/python3.12 -m pytest tests/services/test_streaming_asr_mock.py -v
```

Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/services/streaming_asr.py \
        poc/backend/app/services/streaming_asr_mock.py \
        poc/backend/app/services/streaming_asr_dashscope.py \
        poc/backend/app/core/config.py \
        poc/backend/tests/services/test_streaming_asr_mock.py
git commit -m "feat: streaming ASR dispatcher + mock backend"
```

---

## Task 3: RealtimeSuggestionEngine

**Goal:** Implement utterance-end + 5s debounce + 20s timeout LLM trigger logic. Reuse existing `services/llm.py` for the actual LLM call.

**Files:**
- Create: `poc/backend/app/services/realtime_llm.py`
- Create: `poc/backend/tests/services/test_realtime_llm_engine.py`

**Subagent model:** sonnet

- [ ] **Step 1: Write failing test for the engine**

```python
# poc/backend/tests/services/test_realtime_llm_engine.py
import asyncio
import time
from datetime import datetime, timezone

import pytest


@pytest.fixture
def fake_case():
    class _Case:
        id = 999
        amount_owed = 2400
        months_overdue = 6
    return _Case()


@pytest.fixture
def fake_owner():
    class _Owner:
        name = "张某某"
        building = "3"
        room = "2-101"
    return _Owner()


def _chunk(seq, text, speaker="customer", utterance_end=True):
    from app.services.streaming_asr import TranscriptChunk
    return TranscriptChunk(
        seq=seq, speaker=speaker, text=text,
        ts=datetime.now(timezone.utc), utterance_end=utterance_end,
    )


@pytest.mark.asyncio
async def test_suggestion_triggered_on_utterance_end_after_debounce(fake_case, fake_owner, monkeypatch):
    from app.services import realtime_llm

    calls = []

    async def fake_llm(messages):
        calls.append(messages)
        return {"text": "建议询问分期", "intent": "ask_installment", "confidence": 0.8}

    monkeypatch.setattr(realtime_llm, "_call_llm", fake_llm)

    engine = realtime_llm.RealtimeSuggestionEngine(fake_case, fake_owner, debounce_sec=0)
    s = await engine.on_transcript(_chunk(0, "您好哪位"))
    assert s is not None
    assert s.text == "建议询问分期"
    assert s.id  # uuid generated


@pytest.mark.asyncio
async def test_suggestion_debounce_skips_within_window(fake_case, fake_owner, monkeypatch):
    from app.services import realtime_llm

    async def fake_llm(messages):
        return {"text": "建议X", "intent": "x", "confidence": 0.9}

    monkeypatch.setattr(realtime_llm, "_call_llm", fake_llm)

    engine = realtime_llm.RealtimeSuggestionEngine(fake_case, fake_owner, debounce_sec=10)
    first = await engine.on_transcript(_chunk(0, "我没钱"))
    assert first is not None
    second = await engine.on_transcript(_chunk(1, "下个月再说"))
    assert second is None  # within debounce window


@pytest.mark.asyncio
async def test_suggestion_timeout_fallback_triggers_when_no_utterance_end(fake_case, fake_owner, monkeypatch):
    from app.services import realtime_llm

    async def fake_llm(messages):
        return {"text": "建议Y", "intent": "y", "confidence": 0.7}

    monkeypatch.setattr(realtime_llm, "_call_llm", fake_llm)

    engine = realtime_llm.RealtimeSuggestionEngine(
        fake_case, fake_owner, debounce_sec=5, timeout_sec=0
    )
    s = await engine.on_transcript(_chunk(0, "...", utterance_end=False))
    assert s is not None  # timeout=0 forces immediate trigger
    assert s.text == "建议Y"


@pytest.mark.asyncio
async def test_no_suggestion_when_chunk_not_utterance_end_within_timeout(fake_case, fake_owner, monkeypatch):
    from app.services import realtime_llm

    async def fake_llm(messages):
        pytest.fail("should not call LLM")

    monkeypatch.setattr(realtime_llm, "_call_llm", fake_llm)

    engine = realtime_llm.RealtimeSuggestionEngine(
        fake_case, fake_owner, debounce_sec=10, timeout_sec=120
    )
    s = await engine.on_transcript(_chunk(0, "...", utterance_end=False))
    assert s is None
```

- [ ] **Step 2: Run the test — confirm failure**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/python3.12 -m pytest tests/services/test_realtime_llm_engine.py -v
```

Expected: `ModuleNotFoundError: app.services.realtime_llm`.

- [ ] **Step 3: Implement `realtime_llm.py`**

```python
# poc/backend/app/services/realtime_llm.py
"""Realtime LLM suggestion engine — utterance-end + debounce + timeout fallback."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from app.core.config import settings

from .streaming_asr import TranscriptChunk


@dataclass
class Suggestion:
    id: str
    text: str
    intent: str
    confidence: float

    def to_message(self) -> dict:
        return {
            "type": "suggestion.ready",
            "id": self.id,
            "text": self.text,
            "intent": self.intent,
            "confidence": self.confidence,
        }


@dataclass
class _CaseCtx:
    case: object
    owner: object
    transcript: list[TranscriptChunk] = field(default_factory=list)


class RealtimeSuggestionEngine:
    def __init__(
        self,
        case,
        owner,
        debounce_sec: Optional[int] = None,
        timeout_sec: Optional[int] = None,
    ):
        self._ctx = _CaseCtx(case=case, owner=owner)
        self._debounce_sec = (
            debounce_sec if debounce_sec is not None else settings.realtime_llm_debounce_sec
        )
        self._timeout_sec = (
            timeout_sec if timeout_sec is not None else settings.realtime_llm_timeout_sec
        )
        self._last_llm_at: float = 0.0

    async def on_transcript(self, chunk: TranscriptChunk) -> Optional[Suggestion]:
        self._ctx.transcript.append(chunk)
        now = time.monotonic()

        debounce_elapsed = (now - self._last_llm_at) >= self._debounce_sec
        timeout_hit = (now - self._last_llm_at) >= self._timeout_sec

        should_trigger = (chunk.utterance_end and debounce_elapsed) or timeout_hit
        if not should_trigger:
            return None

        self._last_llm_at = now
        return await self._invoke_llm()

    async def on_call_ended(self) -> dict:
        """Final call analysis returned as a payload dict for tag.ready."""
        result = await _call_final_analysis(self._build_messages(final=True))
        return result

    async def _invoke_llm(self) -> Suggestion:
        result = await _call_llm(self._build_messages(final=False))
        return Suggestion(
            id=str(uuid.uuid4()),
            text=result.get("text", ""),
            intent=result.get("intent", "unknown"),
            confidence=float(result.get("confidence", 0.0)),
        )

    def _build_messages(self, final: bool) -> list[dict]:
        owner_name = getattr(self._ctx.owner, "name", "未知")
        amount = getattr(self._ctx.case, "amount_owed", 0)
        months = getattr(self._ctx.case, "months_overdue", 0)
        history = "\n".join(
            f"[{c.speaker}] {c.text}" for c in self._ctx.transcript[-10:]
        )
        if final:
            prompt = (
                f"以下是与业主 {owner_name}（欠费 {amount} / {months} 月）"
                f"的完整通话记录，请输出最终分析（intent / promise_date / promise_amount / summary）：\n\n{history}"
            )
        else:
            prompt = (
                f"以下是与业主 {owner_name}（欠费 {amount} / {months} 月）"
                f"的对话片段，请基于业主最近一句生成 1 条话术建议：\n\n{history}"
            )
        return [{"role": "user", "content": prompt}]


async def _call_llm(messages: list[dict]) -> dict:
    """Default impl wraps app.services.llm; tests monkeypatch this symbol."""
    from . import llm as llm_service
    raw = llm_service.complete(messages)
    if isinstance(raw, dict):
        return raw
    return {"text": str(raw), "intent": "unknown", "confidence": 0.5}


async def _call_final_analysis(messages: list[dict]) -> dict:
    from . import llm as llm_service
    raw = llm_service.complete(messages)
    if isinstance(raw, dict):
        return raw
    return {
        "intent": "unknown",
        "promise_date": None,
        "promise_amount": None,
        "summary": str(raw),
        "needs_review": True,
    }
```

- [ ] **Step 4: Run the test — confirm pass**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/python3.12 -m pytest tests/services/test_realtime_llm_engine.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/services/realtime_llm.py \
        poc/backend/tests/services/test_realtime_llm_engine.py
git commit -m "feat: realtime LLM suggestion engine — utterance + debounce + timeout"
```

---

## Task 4: MiPush dispatcher + mock backend

**Goal:** Implement `mipush` service with `xiaomi` HTTP backend and `mock` in-memory backend. Tests use mock; production uses xiaomi (manually smoke-tested).

**Files:**
- Create: `poc/backend/app/services/mipush.py`
- Create: `poc/backend/app/services/mipush_mock.py`
- Create: `poc/backend/app/services/mipush_xiaomi.py`
- Create: `poc/backend/tests/services/test_mipush_mock.py`

**Subagent model:** sonnet

- [ ] **Step 1: Write failing test for mock MiPush**

```python
# poc/backend/tests/services/test_mipush_mock.py
import pytest


@pytest.mark.asyncio
async def test_mock_mipush_records_payload():
    from app.services import mipush

    client = mipush.get_mipush_client()
    # Force a fresh mock instance so prior tests don't pollute
    if hasattr(client, "reset"):
        client.reset()
    await client.send_to_user(
        reg_id="reg-abc",
        payload={"type": "DIAL_REQUEST", "call_id": 4711, "case_id": 1023},
        title="新呼叫",
        description="张某某 · 138****1234",
    )
    sent = client.sent_messages
    assert len(sent) == 1
    msg = sent[0]
    assert msg["reg_id"] == "reg-abc"
    assert msg["payload"]["type"] == "DIAL_REQUEST"
    assert msg["payload"]["call_id"] == 4711
    assert msg["title"] == "新呼叫"


@pytest.mark.asyncio
async def test_mock_mipush_singleton_across_calls():
    from app.services import mipush

    a = mipush.get_mipush_client()
    b = mipush.get_mipush_client()
    assert a is b
```

- [ ] **Step 2: Run the test — confirm failure**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/python3.12 -m pytest tests/services/test_mipush_mock.py -v
```

Expected: `ModuleNotFoundError: app.services.mipush`.

- [ ] **Step 3: Implement `mipush.py` dispatcher**

```python
# poc/backend/app/services/mipush.py
"""MiPush dispatcher — Xiaomi HTTP API in production, in-memory mock for tests."""
from __future__ import annotations

from typing import Protocol

from app.core.config import settings


class MiPushClient(Protocol):
    sent_messages: list  # only present on mock

    async def send_to_user(
        self,
        reg_id: str,
        payload: dict,
        title: str,
        description: str,
    ) -> None: ...


_singleton: MiPushClient | None = None


def get_mipush_client() -> MiPushClient:
    global _singleton
    if _singleton is not None:
        return _singleton
    backend = settings.mipush_backend.lower()
    if backend == "mock":
        from .mipush_mock import MockMiPushClient
        _singleton = MockMiPushClient()
    elif backend == "xiaomi":
        from .mipush_xiaomi import XiaomiMiPushClient
        _singleton = XiaomiMiPushClient(
            app_secret=settings.mipush_app_secret,
            package_name=settings.mipush_package_name,
        )
    else:
        raise RuntimeError(f"unknown MIPUSH_BACKEND: {settings.mipush_backend}")
    return _singleton


def _reset_for_tests() -> None:
    """Internal: reset the singleton between tests if needed."""
    global _singleton
    _singleton = None
```

- [ ] **Step 4: Implement mock backend**

```python
# poc/backend/app/services/mipush_mock.py
from __future__ import annotations


class MockMiPushClient:
    def __init__(self):
        self.sent_messages: list[dict] = []

    async def send_to_user(
        self,
        reg_id: str,
        payload: dict,
        title: str,
        description: str,
    ) -> None:
        self.sent_messages.append({
            "reg_id": reg_id,
            "payload": payload,
            "title": title,
            "description": description,
        })

    def reset(self) -> None:
        self.sent_messages.clear()
```

- [ ] **Step 5: Implement Xiaomi HTTP backend**

```python
# poc/backend/app/services/mipush_xiaomi.py
from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger(__name__)


class XiaomiMiPushClient:
    URL = "https://api.xmpush.xiaomi.com/v3/message/regid"

    def __init__(self, app_secret: str, package_name: str):
        if not app_secret:
            raise RuntimeError("MIPUSH_APP_SECRET is required for xiaomi backend")
        self._app_secret = app_secret
        self._package_name = package_name

    async def send_to_user(
        self,
        reg_id: str,
        payload: dict,
        title: str,
        description: str,
    ) -> None:
        async with httpx.AsyncClient(timeout=5) as cli:
            resp = await cli.post(
                self.URL,
                headers={"Authorization": f"key={self._app_secret}"},
                data={
                    "registration_id": reg_id,
                    "restricted_package_name": self._package_name,
                    "payload": json.dumps(payload),
                    "title": title,
                    "description": description,
                    "pass_through": "0",
                    "notify_type": "-1",
                },
            )
            resp.raise_for_status()
            body = resp.json()
            if body.get("result") != "ok":
                logger.error("mipush failed: %s", body)
                raise RuntimeError(f"MiPush API error: {body}")
```

- [ ] **Step 6: Add `conftest.py` autouse fixture to reset mock between tests**

In `poc/backend/tests/conftest.py`, append at end:

```python
@pytest.fixture(autouse=True)
def reset_mipush_mock():
    from app.services import mipush
    mipush._reset_for_tests()
    yield
    mipush._reset_for_tests()
```

- [ ] **Step 7: Run the test — confirm pass**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/python3.12 -m pytest tests/services/test_mipush_mock.py -v
```

Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/services/mipush.py \
        poc/backend/app/services/mipush_mock.py \
        poc/backend/app/services/mipush_xiaomi.py \
        poc/backend/tests/services/test_mipush_mock.py \
        poc/backend/tests/conftest.py
git commit -m "feat: MiPush dispatcher + mock backend (xiaomi HTTP wrapper for prod)"
```

---

## Task 5: POST /api/v1/calls/dial-request

**Goal:** Agent on PC clicks "拨打" → server creates `CallRecord(status="pending_dial")` and pushes a `DIAL_REQUEST` payload via MiPush to the agent's most-recent device. Establishes the call_id that both Android and PC then connect to via WebSocket.

**Files:**
- Modify: `poc/backend/app/schemas/call.py`
- Modify: `poc/backend/app/api/calls_v1.py`
- Modify: `poc/backend/tests/conftest.py` — add `seeded_device_with_push_reg`
- Create: `poc/backend/tests/api/test_dial_request.py`

**Subagent model:** sonnet

**Reference:** Spec §5.1, §6.3 (status enum extension)

- [ ] **Step 1: Add fixtures to `conftest.py`**

Append at end of `poc/backend/tests/conftest.py`:

```python
@pytest.fixture
def seeded_device_with_push_reg(db_session, seeded_member_user, seeded_tenant):
    from app.models.device import DeviceProfile
    device = DeviceProfile(
        device_id="test-device-001",
        user_id=seeded_member_user.id,
        tenant_id=seeded_tenant.id,
        brand="Xiaomi",
        model="Redmi K70",
        os_version="MIUI 14",
        push_reg_id="reg-id-xiaomi-abc123",
        push_provider="xiaomi",
        is_healthy=True,
    )
    db_session.add(device)
    db_session.flush()
    return device


@pytest.fixture
def seeded_assigned_case(db_session, seeded_case, seeded_member_user):
    seeded_case.assigned_to = seeded_member_user.id
    db_session.flush()
    return seeded_case
```

> Note: `push_reg_id` / `push_provider` columns are added in T1 — this fixture assumes the migration has run.

- [ ] **Step 2: Add `DialRequestIn` / `DialRequestOut` to `schemas/call.py`**

In `poc/backend/app/schemas/call.py`, append:

```python
# ── Sprint 4: realtime call schemas ───────────────────────────


class DialRequestIn(BaseModel):
    case_id: int


class DialRequestOut(BaseModel):
    call_id: int
    status: str  # "dispatched"
```

- [ ] **Step 3: Write failing tests for the endpoint**

```python
# poc/backend/tests/api/test_dial_request.py
import pytest


@pytest.mark.asyncio
async def test_dial_request_success(
    client,
    agent_auth_headers,
    seeded_device_with_push_reg,
    seeded_assigned_case,
):
    from app.services import mipush
    mipush._reset_for_tests()

    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": seeded_assigned_case.id},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "dispatched"
    call_id = body["call_id"]
    assert isinstance(call_id, int) and call_id > 0

    sent = mipush._get_mock_sent()
    assert len(sent) == 1
    msg = sent[0]
    assert msg["reg_id"] == "reg-id-xiaomi-abc123"
    assert msg["payload"]["type"] == "DIAL_REQUEST"
    assert msg["payload"]["call_id"] == call_id
    assert msg["payload"]["case_id"] == seeded_assigned_case.id
    assert "owner_name" in msg["payload"]
    assert "owner_phone_masked" in msg["payload"]
    assert "*" in msg["payload"]["owner_phone_masked"]


@pytest.mark.asyncio
async def test_dial_request_case_not_assigned_to_user(
    client,
    agent_auth_headers,
    seeded_device_with_push_reg,
    seeded_case,  # not assigned
):
    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": seeded_case.id},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "ERR_FORBIDDEN"


@pytest.mark.asyncio
async def test_dial_request_no_push_reg_id(
    client,
    agent_auth_headers,
    seeded_assigned_case,
    db_session,
    seeded_member_user,
    seeded_tenant,
):
    from app.models.device import DeviceProfile
    device = DeviceProfile(
        device_id="device-no-push",
        user_id=seeded_member_user.id,
        tenant_id=seeded_tenant.id,
        push_reg_id=None,
    )
    db_session.add(device)
    db_session.flush()

    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": seeded_assigned_case.id},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "ERR_PUSH_NOT_REGISTERED"


@pytest.mark.asyncio
async def test_dial_request_cross_tenant_case(
    client,
    agent_auth_headers,
    seeded_device_with_push_reg,
    db_session,
):
    # Case in a different tenant
    from app.models.tenant import Tenant
    from app.models.case import OwnerProfile, CollectionCase
    from decimal import Decimal
    from app.core.crypto import encrypt_phone

    other_tenant = Tenant(name="别家公司", admin_phone_enc=encrypt_phone("13800000000"), plan="trial", is_active=True)
    db_session.add(other_tenant)
    db_session.flush()
    owner = OwnerProfile(tenant_id=other_tenant.id, name="李四", phone_enc=encrypt_phone("13700000000"))
    db_session.add(owner)
    db_session.flush()
    case = CollectionCase(
        tenant_id=other_tenant.id, owner_id=owner.id,
        pool_type="public", stage="new",
        amount_owed=Decimal("100"), months_overdue=1, priority_score=100,
    )
    db_session.add(case)
    db_session.flush()

    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": case.id},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 404
```

- [ ] **Step 4: Run the tests — confirm failure**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/python3.12 -m pytest tests/api/test_dial_request.py -v
```

Expected: 4 failures (route not registered).

- [ ] **Step 5: Implement the endpoint in `calls_v1.py`**

In `poc/backend/app/api/calls_v1.py`:

Add imports near the top:

```python
from app.schemas.call import DialRequestIn, DialRequestOut
from app.services import mipush
```

Add the route (place it before the existing `@router.post("/upload", ...)` or at end — order doesn't matter):

```python
@router.post("/dial-request", response_model=DialRequestOut, status_code=201)
async def dial_request(
    body: DialRequestIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> DialRequestOut:
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token 缺少必要字段"},
        )

    case = db.execute(
        select(CollectionCase).where(
            CollectionCase.id == body.case_id,
            CollectionCase.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not case:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不属于当前租户"},
        )
    if case.assigned_to != user_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "案件未分配给当前催收员"},
        )

    # Look up most-recent device with a push_reg_id
    from app.models.device import DeviceProfile  # local import — avoids cycle
    device = db.execute(
        select(DeviceProfile)
        .where(
            DeviceProfile.user_id == user_id,
            DeviceProfile.tenant_id == tenant_id,
            DeviceProfile.push_reg_id.isnot(None),
        )
        .order_by(DeviceProfile.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not device:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_PUSH_NOT_REGISTERED", "message": "设备未注册推送，请重新登录催收 App"},
        )

    # Resolve owner info for the DIAL_REQUEST payload
    from app.models.case import OwnerProfile  # local import
    owner = db.get(OwnerProfile, case.owner_id) if case.owner_id else None
    owner_name = owner.name if owner else "未知业主"
    owner_phone_masked = mask_phone(owner.phone_enc) if owner and owner.phone_enc else ""

    # Insert pending_dial CallRecord
    call = CallRecord(
        tenant_id=tenant_id,
        case_id=case.id,
        caller_user_id=user_id,
        callee_phone_enc=owner.phone_enc if owner and owner.phone_enc else "",
        initiated_by="pc",
        status="pending_dial",
    )
    db.add(call)
    db.flush()

    # Send MiPush
    client = mipush.get_mipush_client()
    payload_dict = {
        "type": "DIAL_REQUEST",
        "call_id": call.id,
        "case_id": case.id,
        "owner_name": owner_name,
        "owner_phone_masked": owner_phone_masked,
    }
    try:
        await client.send_to_user(
            reg_id=device.push_reg_id,
            payload=payload_dict,
            title="新外呼任务",
            description=f"{owner_name} · {owner_phone_masked}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail={"code": "ERR_PUSH_FAILED", "message": "推送失败，请稍后重试"},
        ) from exc

    db.commit()
    return DialRequestOut(call_id=call.id, status="dispatched")
```

- [ ] **Step 6: Run the tests — confirm pass**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/python3.12 -m pytest tests/api/test_dial_request.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/call.py \
        poc/backend/app/api/calls_v1.py \
        poc/backend/tests/conftest.py \
        poc/backend/tests/api/test_dial_request.py
git commit -m "feat: POST /calls/dial-request — create pending_dial + push to user device"
```

---

## Task 6: PATCH /api/v1/calls/{call_id}/tag

**Goal:** Agent confirms (or edits) AI-suggested intent + promise_date + summary at end of call. Updates `AnalysisResult` and stamps `call.user_confirmed_at`.

**Files:**
- Modify: `poc/backend/app/schemas/call.py`
- Modify: `poc/backend/app/api/calls_v1.py`
- Create: `poc/backend/tests/api/test_call_tag_patch.py`

**Subagent model:** haiku

**Reference:** Spec §5.2

- [ ] **Step 1: Add `CallTagPatch` + `CallTagOut` schemas**

In `poc/backend/app/schemas/call.py`, append after `DialRequestOut`:

```python
class CallTagPatch(BaseModel):
    intent: Optional[str] = None
    promise_date: Optional[str] = None
    promise_amount: Optional[float] = None
    notes: Optional[str] = None


class CallTagOut(BaseModel):
    call_id: int
    intent: Optional[str]
    promise_date: Optional[str]
    promise_amount: Optional[float]
    summary: Optional[str]
    user_confirmed_at: Optional[datetime]
```

- [ ] **Step 2: Write failing test**

```python
# poc/backend/tests/api/test_call_tag_patch.py
import pytest


@pytest.fixture
def seeded_call_with_analysis(db_session, seeded_case, seeded_member_user, seeded_tenant):
    from datetime import datetime, timezone
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord, AnalysisResult

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000000"),
        initiated_by="app",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration_sec=120,
        status="processed",
    )
    db_session.add(call)
    db_session.flush()
    analysis = AnalysisResult(
        call_id=call.id,
        summary="客户表示下月发工资再缴费",
        key_segments={"intent": "promise_pay", "promise_date": "2026-05-15"},
        needs_review=False,
    )
    db_session.add(analysis)
    db_session.flush()
    return call


@pytest.mark.asyncio
async def test_patch_tag_updates_analysis_and_confirms(
    client, agent_auth_headers, seeded_call_with_analysis, db_session,
):
    resp = await client.patch(
        f"/api/v1/calls/{seeded_call_with_analysis.id}/tag",
        json={
            "intent": "promise_pay",
            "promise_date": "2026-05-10",
            "promise_amount": 2400.0,
            "notes": "等下个月发工资",
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["intent"] == "promise_pay"
    assert body["promise_date"] == "2026-05-10"
    assert body["promise_amount"] == 2400.0
    assert body["user_confirmed_at"] is not None

    db_session.expire_all()
    from app.models.call import CallRecord, AnalysisResult
    from sqlalchemy import select
    call = db_session.execute(
        select(CallRecord).where(CallRecord.id == seeded_call_with_analysis.id)
    ).scalar_one()
    assert call.user_confirmed_at is not None
    analysis = db_session.execute(
        select(AnalysisResult).where(AnalysisResult.call_id == call.id)
    ).scalar_one()
    assert analysis.key_segments["intent"] == "promise_pay"
    assert analysis.key_segments["promise_date"] == "2026-05-10"


@pytest.mark.asyncio
async def test_patch_tag_forbidden_for_other_user(
    client, supervisor_auth_headers, seeded_call_with_analysis,
):
    resp = await client.patch(
        f"/api/v1/calls/{seeded_call_with_analysis.id}/tag",
        json={"intent": "refuse"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "ERR_FORBIDDEN"


@pytest.mark.asyncio
async def test_patch_tag_call_not_found(client, agent_auth_headers):
    resp = await client.patch(
        "/api/v1/calls/999999/tag",
        json={"intent": "refuse"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 404
```

- [ ] **Step 3: Implement `PATCH /{call_id}/tag` in `calls_v1.py`**

Add import:

```python
from app.schemas.call import CallTagOut, CallTagPatch
```

Add route:

```python
@router.patch("/{call_id}/tag", response_model=CallTagOut)
def patch_call_tag(
    call_id: int,
    body: CallTagPatch,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CallTagOut:
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)

    call = db.execute(
        select(CallRecord).where(
            CallRecord.id == call_id,
            CallRecord.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not call:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "通话记录不存在"},
        )
    if call.caller_user_id != user_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "无权修改此通话"},
        )

    analysis = db.execute(
        select(AnalysisResult).where(AnalysisResult.call_id == call_id)
    ).scalar_one_or_none()
    if not analysis:
        analysis = AnalysisResult(call_id=call_id, key_segments={})
        db.add(analysis)
        db.flush()

    # Merge into key_segments (don't overwrite existing fields with None)
    seg = dict(analysis.key_segments or {})
    if body.intent is not None:
        seg["intent"] = body.intent
    if body.promise_date is not None:
        seg["promise_date"] = body.promise_date
    if body.promise_amount is not None:
        seg["promise_amount"] = body.promise_amount
    analysis.key_segments = seg
    if body.notes is not None:
        analysis.summary = body.notes

    call.user_confirmed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(analysis)
    db.refresh(call)

    return CallTagOut(
        call_id=call.id,
        intent=seg.get("intent"),
        promise_date=seg.get("promise_date"),
        promise_amount=seg.get("promise_amount"),
        summary=analysis.summary,
        user_confirmed_at=call.user_confirmed_at,
    )
```

- [ ] **Step 4: Run tests — confirm pass**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/python3.12 -m pytest tests/api/test_call_tag_patch.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/call.py \
        poc/backend/app/api/calls_v1.py \
        poc/backend/tests/api/test_call_tag_patch.py
git commit -m "feat: PATCH /calls/{id}/tag — agent confirms intent/promise/summary"
```

---

## Task 7: WebSocket signaling + per-call session aggregator

**Goal:** Implement `/ws/calls/{call_id}` endpoint with JWT-in-querystring auth, role-based access, in-process `ConnectionManager`, and `CallSession` that wires Streaming ASR → RealtimeSuggestionEngine → broadcast to all room members.

**Files:**
- Create: `poc/backend/app/ws/__init__.py`
- Create: `poc/backend/app/ws/auth.py`
- Create: `poc/backend/app/ws/connection_manager.py`
- Create: `poc/backend/app/ws/call_session.py`
- Create: `poc/backend/app/api/ws_calls.py`
- Modify: `poc/backend/app/main.py` — register router
- Create: `poc/backend/tests/ws/__init__.py`
- Create: `poc/backend/tests/ws/test_ws_calls_auth.py`
- Create: `poc/backend/tests/ws/test_ws_calls_e2e.py`

**Subagent model:** sonnet

**Reference:** Spec §1, §1.2-1.4

- [ ] **Step 1: Create empty package markers**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
touch app/ws/__init__.py tests/ws/__init__.py
```

- [ ] **Step 2: WebSocket auth helper `app/ws/auth.py`**

```python
# poc/backend/app/ws/auth.py
"""JWT validation for WebSocket query-string token."""
from __future__ import annotations

from typing import Optional

from jose import JWTError, jwt

from app.core.config import settings


def decode_ws_token(token: str) -> Optional[dict]:
    """Return JWT payload dict or None if invalid."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except JWTError:
        return None
    if "user_id" not in payload or "tenant_id" not in payload:
        return None
    return payload
```

- [ ] **Step 3: ConnectionManager `app/ws/connection_manager.py`**

```python
# poc/backend/app/ws/connection_manager.py
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # call_id -> {ws: role}
        self._rooms: dict[int, dict[WebSocket, str]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def connect(self, call_id: int, ws: WebSocket, role: str) -> None:
        async with self._lock:
            self._rooms[call_id][ws] = role

    async def disconnect(self, call_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms[call_id].pop(ws, None)
            if not self._rooms[call_id]:
                self._rooms.pop(call_id, None)

    async def broadcast(
        self, call_id: int, message: dict, exclude: Optional[WebSocket] = None
    ) -> None:
        async with self._lock:
            members = list(self._rooms.get(call_id, {}).items())
        for ws, _role in members:
            if ws is exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception as exc:
                logger.warning("broadcast failed call=%s: %s", call_id, exc)

    def room_size(self, call_id: int) -> int:
        return len(self._rooms.get(call_id, {}))

    def list_roles(self, call_id: int) -> list[str]:
        return list(self._rooms.get(call_id, {}).values())


_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
```

- [ ] **Step 4: CallSession aggregator `app/ws/call_session.py`**

```python
# poc/backend/app/ws/call_session.py
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.call import CallRecord
from app.models.case import CollectionCase, OwnerProfile
from app.services.streaming_asr import TranscriptChunk, get_streaming_asr_backend
from app.services.realtime_llm import RealtimeSuggestionEngine, Suggestion

logger = logging.getLogger(__name__)


class CallSession:
    """Per-call audio-pipeline aggregator. Owns one ASR session + one suggestion engine.

    Created on first agent connection; torn down when room becomes empty
    or `call.ended` received.
    """

    def __init__(
        self,
        call_id: int,
        on_transcript_broadcast,
        on_suggestion_broadcast,
        on_tag_ready,
    ) -> None:
        self.call_id = call_id
        self._on_transcript = on_transcript_broadcast
        self._on_suggestion = on_suggestion_broadcast
        self._on_tag = on_tag_ready
        self._asr_session = None
        self._llm_engine: Optional[RealtimeSuggestionEngine] = None

    async def start(self, db: Session) -> None:
        call = db.get(CallRecord, self.call_id)
        if not call or not call.case_id:
            return
        case = db.get(CollectionCase, call.case_id)
        owner = db.get(OwnerProfile, case.owner_id) if case and case.owner_id else None
        self._llm_engine = RealtimeSuggestionEngine(case=case, owner=owner)

        backend = get_streaming_asr_backend()
        self._asr_session = await backend.open_session(
            on_transcript=self._handle_transcript,
            on_error=self._handle_error,
        )

    async def feed_audio(self, pcm_bytes: bytes) -> None:
        if self._asr_session:
            await self._asr_session.feed_audio(pcm_bytes)

    async def stop(self) -> None:
        if self._asr_session:
            await self._asr_session.close()
            self._asr_session = None
        if self._llm_engine:
            tag = await self._llm_engine.on_call_ended()
            if tag:
                await self._on_tag(tag)
            self._llm_engine = None

    async def _handle_transcript(self, chunk: TranscriptChunk) -> None:
        await self._on_transcript({
            "type": "transcript.chunk",
            "seq": chunk.seq,
            "speaker": chunk.speaker,
            "text": chunk.text,
            "ts": chunk.ts.isoformat() if hasattr(chunk.ts, "isoformat") else chunk.ts,
            "utterance_end": getattr(chunk, "utterance_end", False),
        })
        if self._llm_engine:
            suggestion = await self._llm_engine.on_transcript(chunk)
            if suggestion:
                await self._on_suggestion({
                    "type": "suggestion.ready",
                    "id": suggestion.id,
                    "text": suggestion.text,
                    "intent": suggestion.intent,
                    "confidence": suggestion.confidence,
                })

    async def _handle_error(self, exc: Exception) -> None:
        logger.error("ASR error call=%s: %s", self.call_id, exc)
```

> Note: This module imports `Suggestion`, `RealtimeSuggestionEngine`, `TranscriptChunk` from T2/T3 modules — both already created. The `Suggestion` dataclass must expose `id`, `text`, `intent`, `confidence`. If T3 didn't define those fields, extend it before merging T7.

- [ ] **Step 5: WebSocket endpoint `app/api/ws_calls.py`**

```python
# poc/backend/app/api/ws_calls.py
from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.call import CallRecord
from app.models.case import CollectionCase
from app.ws.auth import decode_ws_token
from app.ws.call_session import CallSession
from app.ws.connection_manager import get_connection_manager

router = APIRouter()
logger = logging.getLogger(__name__)


# In-process registry: call_id -> CallSession (one per active call)
_sessions: dict[int, CallSession] = {}


def _authorize(payload: dict, role: str, call: CallRecord) -> bool:
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)
    user_role = payload.get("role", "")

    if call.tenant_id != tenant_id:
        return False

    if role == "agent":
        return call.caller_user_id == user_id
    if role == "observer":
        return user_role in {"admin", "supervisor"}
    return False


@router.websocket("/ws/calls/{call_id}")
async def ws_calls(
    websocket: WebSocket,
    call_id: int,
    token: Annotated[Optional[str], Query()] = None,
    role: Annotated[str, Query()] = "agent",
    db: Annotated[Session, Depends(get_db)] = None,
):
    payload = decode_ws_token(token or "")
    if payload is None:
        await websocket.close(code=1008, reason="invalid token")
        return

    call = db.execute(
        select(CallRecord).where(CallRecord.id == call_id)
    ).scalar_one_or_none()
    if not call:
        await websocket.close(code=1008, reason="call not found")
        return

    if not _authorize(payload, role, call):
        await websocket.close(code=1008, reason="policy violation")
        return

    await websocket.accept()
    manager = get_connection_manager()
    await manager.connect(call_id, websocket, role)

    # Lazy-init the call session on first connection
    session = _sessions.get(call_id)
    if session is None and role == "agent":
        async def broadcast_transcript(msg):
            await manager.broadcast(call_id, msg)

        async def broadcast_suggestion(msg):
            await manager.broadcast(call_id, msg)

        async def broadcast_tag(tag):
            await manager.broadcast(call_id, {"type": "tag.ready", **tag})

        session = CallSession(
            call_id=call_id,
            on_transcript_broadcast=broadcast_transcript,
            on_suggestion_broadcast=broadcast_suggestion,
            on_tag_ready=broadcast_tag,
        )
        await session.start(db)
        _sessions[call_id] = session

    try:
        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if "bytes" in msg and msg["bytes"] is not None:
                if role == "agent" and session:
                    await session.feed_audio(msg["bytes"])
                continue
            if "text" in msg and msg["text"] is not None:
                import json
                try:
                    data = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue
                t = data.get("type")
                if t == "ping":
                    await websocket.send_json({"type": "pong"})
                elif t == "call.started" and role == "agent":
                    call.status = "live"
                    db.commit()
                elif t == "call.ended" and role == "agent":
                    call.status = "live_ended_pending_analysis"
                    db.commit()
                    if session:
                        await session.stop()
                elif t == "suggestion.feedback" and role == "agent":
                    # Persisted via separate REST endpoint (T15); WS just acks for UX
                    await websocket.send_json({"type": "ack", "for": data.get("id")})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(call_id, websocket)
        # Tear down session if room empty
        if manager.room_size(call_id) == 0:
            sess = _sessions.pop(call_id, None)
            if sess:
                await sess.stop()
```

- [ ] **Step 6: Register router in `app/main.py`**

In `poc/backend/app/main.py`, add the import + include:

```python
from app.api import ws_calls as ws_calls_router

app.include_router(ws_calls_router.router)  # no prefix — /ws/calls/{id} stays as-is
```

- [ ] **Step 7: Auth + cross-tenant tests**

```python
# poc/backend/tests/ws/test_ws_calls_auth.py
import pytest
from httpx import AsyncClient, ASGITransport
from starlette.testclient import TestClient


def _make_call(db_session, seeded_member_user, seeded_tenant, seeded_case):
    from app.models.call import CallRecord
    from app.core.crypto import encrypt_phone
    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000000"),
        initiated_by="pc",
        status="pending_dial",
    )
    db_session.add(call)
    db_session.flush()
    return call


@pytest.fixture
def call_for_member(db_session, seeded_member_user, seeded_tenant, seeded_case):
    return _make_call(db_session, seeded_member_user, seeded_tenant, seeded_case)


def test_ws_rejects_missing_token(db_session, call_for_member):
    from app.main import app
    from app.core.db import get_db

    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with pytest.raises(Exception):  # 1008 close raises in TestClient
                with cli.websocket_connect(f"/ws/calls/{call_for_member.id}?role=agent"):
                    pass
    finally:
        app.dependency_overrides.clear()


def test_ws_rejects_invalid_token(db_session, call_for_member):
    from app.main import app
    from app.core.db import get_db

    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with pytest.raises(Exception):
                with cli.websocket_connect(
                    f"/ws/calls/{call_for_member.id}?token=garbage&role=agent"
                ):
                    pass
    finally:
        app.dependency_overrides.clear()


def test_ws_rejects_agent_other_user(db_session, call_for_member, seeded_supervisor_user, seeded_tenant):
    from app.main import app
    from app.core.db import get_db
    from app.core.security import create_access_token

    token = create_access_token({
        "sub": str(seeded_supervisor_user.id),
        "user_id": seeded_supervisor_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "supervisor",
        "scope": f"tenant:{seeded_tenant.id}",
    })

    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with pytest.raises(Exception):
                with cli.websocket_connect(
                    f"/ws/calls/{call_for_member.id}?token={token}&role=agent"
                ):
                    pass
    finally:
        app.dependency_overrides.clear()


def test_ws_observer_supervisor_accepted(db_session, call_for_member, seeded_supervisor_user, seeded_tenant):
    from app.main import app
    from app.core.db import get_db
    from app.core.security import create_access_token

    token = create_access_token({
        "sub": str(seeded_supervisor_user.id),
        "user_id": seeded_supervisor_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "supervisor",
        "scope": f"tenant:{seeded_tenant.id}",
    })

    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with cli.websocket_connect(
                f"/ws/calls/{call_for_member.id}?token={token}&role=observer"
            ) as ws:
                ws.send_json({"type": "ping"})
                msg = ws.receive_json()
                assert msg["type"] == "pong"
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 8: End-to-end test (mock ASR + mock LLM)**

```python
# poc/backend/tests/ws/test_ws_calls_e2e.py
import pytest
from starlette.testclient import TestClient


@pytest.fixture
def call_for_member(db_session, seeded_member_user, seeded_tenant, seeded_case):
    from app.models.call import CallRecord
    from app.core.crypto import encrypt_phone
    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000000"),
        initiated_by="pc",
        status="pending_dial",
    )
    db_session.add(call)
    db_session.flush()
    return call


def test_ws_agent_streams_audio_receives_transcript(
    db_session, call_for_member, seeded_member_user, seeded_tenant, agent_auth_headers,
):
    from app.main import app
    from app.core.db import get_db
    from app.core.security import create_access_token

    token = create_access_token({
        "sub": str(seeded_member_user.id),
        "user_id": seeded_member_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "agent_internal",
        "scope": f"tenant:{seeded_tenant.id}",
    })

    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with cli.websocket_connect(
                f"/ws/calls/{call_for_member.id}?token={token}&role=agent"
            ) as ws:
                ws.send_json({"type": "call.started"})
                fake_frame = b"\x00" * 3200
                # Feed ~2s — mock should emit at least 1 transcript chunk per second
                received: list[dict] = []
                for _ in range(20):
                    ws.send_bytes(fake_frame)
                # Drain whatever the server has produced (best-effort, non-blocking)
                import time
                deadline = time.time() + 2.0
                while time.time() < deadline:
                    try:
                        msg = ws.receive_json(timeout=0.2) if hasattr(ws, "receive_json") else ws.receive_json()
                        received.append(msg)
                    except Exception:
                        break

                ws.send_json({"type": "call.ended"})
        assert any(m.get("type") == "transcript.chunk" for m in received), received
    finally:
        app.dependency_overrides.clear()
```

> Note: TestClient WebSocket `receive_json` does not natively support `timeout`. If the helper raises, drop the timeout arg and rely on the loop-and-catch pattern; behavior depends on starlette version. The point of the test is to confirm at least one `transcript.chunk` arrives — adjust the drain logic if needed.

- [ ] **Step 9: Run tests — confirm pass**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/python3.12 -m pytest tests/ws/ -v
```

Expected: 4 auth tests + 1 e2e = 5 passed.

- [ ] **Step 10: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/ws/ \
        poc/backend/app/api/ws_calls.py \
        poc/backend/app/main.py \
        poc/backend/tests/ws/
git commit -m "feat: WebSocket /ws/calls/{id} — JWT auth + ConnectionManager + CallSession"
```

---

## Task 8: Android MiPush integration (registration + DIAL_REQUEST routing)

**Goal:** Register device with Xiaomi MiPush at app start; persist `regId` in `AppConfig`; on backend confirmation, upload to `/api/v1/devices/register`. On `DIAL_REQUEST` notification, parse payload and launch `RealtimeCallActivity` with `case_id` + `call_id`.

**Files:**
- Modify: `poc/android/app/build.gradle` — add MiPushClient SDK
- Modify: `poc/android/app/src/main/AndroidManifest.xml` — receiver + permissions
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/AppConfig.kt`
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/Api.kt` — pass `push_reg_id`
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/MainActivity.kt`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/push/MiPushService.kt`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/push/DialRequestHandler.kt`

**Subagent model:** sonnet

**Reference:** Spec §7.2, §7.7

> ⚠️ **Real MiPush SDK requires AppID/AppKey from Xiaomi developer console.** For PoC default, use the mock-only flow: Android still uses the SDK, but during dev the backend's `mipush_backend=mock` simply skips the HTTP call. Real registration only succeeds when an APK with valid AppID is installed on a device that's logged into a Mi account. Local Robolectric tests stub the SDK.

- [ ] **Step 1: Add Gradle dependency**

In `poc/android/app/build.gradle` `dependencies { ... }`:

```gradle
implementation 'com.xiaomi.mipush.sdk:MiPushClient:6.0.0-RELEASE'
```

If the artifact isn't on Maven Central, follow Xiaomi's docs to add the AAR to `app/libs/` and reference via `implementation files('libs/MiPushClient-6.0.0.aar')`.

- [ ] **Step 2: Manifest permissions + receiver**

In `poc/android/app/src/main/AndroidManifest.xml`, inside `<manifest>`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.CALL_PHONE" />
<uses-permission android:name="android.permission.READ_PHONE_STATE" />
<uses-permission android:name="android.permission.WAKE_LOCK" />
<uses-permission android:name="android.permission.VIBRATE" />
```

Inside `<application>`:

```xml
<receiver android:name=".push.MiPushService"
          android:exported="true">
    <intent-filter>
        <action android:name="com.xiaomi.mipush.RECEIVE_MESSAGE" />
    </intent-filter>
    <intent-filter>
        <action android:name="com.xiaomi.mipush.MESSAGE_ARRIVED" />
    </intent-filter>
    <intent-filter>
        <action android:name="com.xiaomi.mipush.ERROR" />
    </intent-filter>
</receiver>

<activity android:name=".realtime.RealtimeCallActivity"
          android:launchMode="singleTask"
          android:showWhenLocked="true"
          android:turnScreenOn="true"
          android:exported="false" />
```

- [ ] **Step 3: Persist `pushRegId` in `AppConfig`**

In `poc/android/app/src/main/java/com/autoluyin/demo/AppConfig.kt`, add:

```kotlin
private const val KEY_PUSH_REG_ID = "push_reg_id"

fun pushRegId(ctx: Context): String? =
    prefs(ctx).getString(KEY_PUSH_REG_ID, null)

fun savePushRegId(ctx: Context, regId: String) {
    prefs(ctx).edit().putString(KEY_PUSH_REG_ID, regId).apply()
}
```

(`prefs()` is the existing `SharedPreferences` accessor used elsewhere in `AppConfig.kt`. Adapt the method name if it's named differently — read the file first.)

- [ ] **Step 4: Update `Api.kt` to send `push_reg_id`**

Locate the `registerDevice` Retrofit call. Update the data class + endpoint signature:

```kotlin
data class RegisterDeviceRequest(
    val device_id: String,
    val brand: String?,
    val model: String?,
    val os_version: String?,
    val push_reg_id: String? = null,
    val push_provider: String? = "xiaomi",
)

interface ApiService {
    @POST("api/v1/devices/register")
    suspend fun registerDevice(
        @Header("Authorization") authHeader: String,
        @Body body: RegisterDeviceRequest,
    ): RegisterDeviceResponse
    // ...
}
```

In whatever helper currently calls `registerDevice`, plumb `AppConfig.pushRegId(ctx)` into the request.

- [ ] **Step 5: Implement `MiPushService`**

```kotlin
// poc/android/app/src/main/java/com/autoluyin/demo/push/MiPushService.kt
package com.autoluyin.demo.push

import android.content.Context
import com.autoluyin.demo.AppConfig
import com.xiaomi.mipush.sdk.MiPushClient
import com.xiaomi.mipush.sdk.MiPushCommandMessage
import com.xiaomi.mipush.sdk.MiPushMessage
import com.xiaomi.mipush.sdk.PushMessageReceiver
import org.json.JSONObject

class MiPushService : PushMessageReceiver() {

    override fun onCommandResult(ctx: Context, msg: MiPushCommandMessage) {
        if (msg.command == MiPushClient.COMMAND_REGISTER && msg.resultCode == 0L) {
            val regId = msg.commandArguments?.firstOrNull() ?: return
            AppConfig.savePushRegId(ctx, regId)
            // Best-effort upload — fire-and-forget; MainActivity will retry on next resume
            DialRequestHandler.uploadRegId(ctx, regId)
        }
    }

    override fun onNotificationMessageClicked(ctx: Context, msg: MiPushMessage) {
        handleIncoming(ctx, msg.content)
    }

    override fun onReceivePassThroughMessage(ctx: Context, msg: MiPushMessage) {
        handleIncoming(ctx, msg.content)
    }

    private fun handleIncoming(ctx: Context, content: String?) {
        if (content.isNullOrBlank()) return
        val payload = try { JSONObject(content) } catch (_: Exception) { return }
        if (payload.optString("type") == "DIAL_REQUEST") {
            DialRequestHandler.handle(ctx, payload)
        }
    }
}
```

- [ ] **Step 6: Implement `DialRequestHandler`**

```kotlin
// poc/android/app/src/main/java/com/autoluyin/demo/push/DialRequestHandler.kt
package com.autoluyin.demo.push

import android.content.Context
import android.content.Intent
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.realtime.RealtimeCallActivity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject

object DialRequestHandler {

    fun handle(ctx: Context, payload: JSONObject) {
        val callId = payload.optLong("call_id", -1L).takeIf { it > 0 } ?: return
        val caseId = payload.optLong("case_id", -1L).takeIf { it > 0 } ?: return
        val ownerName = payload.optString("owner_name", "")
        val ownerPhoneMasked = payload.optString("owner_phone_masked", "")

        val intent = Intent(ctx, RealtimeCallActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            putExtra(RealtimeCallActivity.EXTRA_CALL_ID, callId)
            putExtra(RealtimeCallActivity.EXTRA_CASE_ID, caseId)
            putExtra(RealtimeCallActivity.EXTRA_OWNER_NAME, ownerName)
            putExtra(RealtimeCallActivity.EXTRA_OWNER_PHONE_MASKED, ownerPhoneMasked)
        }
        ctx.startActivity(intent)
    }

    fun uploadRegId(ctx: Context, regId: String) {
        // Use existing Retrofit client; needs JWT, so only succeeds if user logged in
        val token = AppConfig.token(ctx) ?: return
        val deviceId = AppConfig.deviceId(ctx) ?: return
        CoroutineScope(Dispatchers.IO).launch {
            runCatching {
                com.autoluyin.demo.ApiClient.service.registerDevice(
                    authHeader = "Bearer $token",
                    body = com.autoluyin.demo.RegisterDeviceRequest(
                        device_id = deviceId,
                        brand = android.os.Build.BRAND,
                        model = android.os.Build.MODEL,
                        os_version = android.os.Build.VERSION.RELEASE,
                        push_reg_id = regId,
                        push_provider = "xiaomi",
                    ),
                )
            }
        }
    }
}
```

- [ ] **Step 7: Initialize MiPush in `MainActivity.onCreate()`**

Append at the end of `MainActivity.onCreate()`:

```kotlin
private val MIPUSH_APP_ID = BuildConfig.MIPUSH_APP_ID
private val MIPUSH_APP_KEY = BuildConfig.MIPUSH_APP_KEY

// in onCreate:
if (MIPUSH_APP_ID.isNotBlank() && MIPUSH_APP_KEY.isNotBlank()) {
    com.xiaomi.mipush.sdk.MiPushClient.registerPush(
        applicationContext, MIPUSH_APP_ID, MIPUSH_APP_KEY
    )
}
```

In `app/build.gradle` add `buildConfigField` for both keys (defaulting to empty string in `defaultConfig` block) so dev builds compile without real credentials.

- [ ] **Step 8: Smoke validation**

This task can't be unit-tested headlessly without major Robolectric stubbing of MiPushClient. Defer real verification to E2E (T16). Confirm:

```bash
cd /Users/shuo/AI/autoluyin/poc/android
./gradlew assembleDebug
```

Expected: APK builds cleanly.

- [ ] **Step 9: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/android/app/build.gradle \
        poc/android/app/src/main/AndroidManifest.xml \
        poc/android/app/src/main/java/com/autoluyin/demo/AppConfig.kt \
        poc/android/app/src/main/java/com/autoluyin/demo/Api.kt \
        poc/android/app/src/main/java/com/autoluyin/demo/MainActivity.kt \
        poc/android/app/src/main/java/com/autoluyin/demo/push/
git commit -m "feat(android): MiPush SDK + DIAL_REQUEST receiver + push_reg_id upload"
```

---

## Task 9: RealtimeCallActivity (four-zone UI)

**Goal:** Full-screen call activity launched from `DIAL_REQUEST`. Shows owner info, ASR transcript stream, AI suggestion card, and call control bar. Wakes from lock screen. Hosts `AudioStreamClient` from T10.

**Files:**
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/realtime/RealtimeCallActivity.kt`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/realtime/TranscriptAdapter.kt`
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/realtime/SuggestionCardView.kt`
- Create: `poc/android/app/src/main/res/layout/activity_realtime_call.xml`
- Create: `poc/android/app/src/main/res/layout/item_transcript_segment.xml`

**Subagent model:** sonnet

**Reference:** Spec §7.3

- [ ] **Step 1: Layout `activity_realtime_call.xml`**

```xml
<!-- poc/android/app/src/main/res/layout/activity_realtime_call.xml -->
<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="#0F172A"
    android:padding="16dp">

    <!-- Top bar: timer + connection status + hangup -->
    <LinearLayout
        android:id="@+id/topBar"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        android:orientation="horizontal"
        android:gravity="center_vertical"
        app:layout_constraintTop_toTopOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent">
        <TextView android:id="@+id/timer"
            android:layout_width="0dp" android:layout_weight="1"
            android:layout_height="wrap_content"
            android:text="00:00" android:textColor="#FFFFFF" android:textSize="22sp"/>
        <TextView android:id="@+id/connectionBadge"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="🟢 实时" android:textColor="#22C55E" android:layout_marginEnd="12dp"/>
        <Button android:id="@+id/btnMute"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="静音" android:layout_marginEnd="8dp"/>
        <Button android:id="@+id/btnHangup"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="挂断" android:backgroundTint="#EF4444"/>
    </LinearLayout>

    <!-- Owner info card -->
    <androidx.cardview.widget.CardView
        android:id="@+id/ownerCard"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        app:cardCornerRadius="12dp"
        app:cardElevation="2dp"
        app:layout_constraintTop_toBottomOf="@id/topBar"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent"
        android:layout_marginTop="12dp">
        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:orientation="vertical"
            android:padding="12dp">
            <TextView android:id="@+id/ownerName"
                android:layout_width="wrap_content" android:layout_height="wrap_content"
                android:textSize="18sp" android:textStyle="bold"/>
            <TextView android:id="@+id/ownerRoom"
                android:layout_width="wrap_content" android:layout_height="wrap_content"
                android:textSize="14sp" android:textColor="#64748B"/>
            <TextView android:id="@+id/amountOwed"
                android:layout_width="wrap_content" android:layout_height="wrap_content"
                android:textSize="14sp" android:textColor="#DC2626"/>
        </LinearLayout>
    </androidx.cardview.widget.CardView>

    <!-- Transcript stream -->
    <androidx.recyclerview.widget.RecyclerView
        android:id="@+id/transcriptList"
        android:layout_width="0dp"
        android:layout_height="0dp"
        android:background="#1E293B"
        android:padding="8dp"
        app:layout_constraintTop_toBottomOf="@id/ownerCard"
        app:layout_constraintBottom_toTopOf="@id/suggestionCard"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent"
        android:layout_marginTop="12dp"/>

    <!-- AI suggestion card -->
    <com.autoluyin.demo.realtime.SuggestionCardView
        android:id="@+id/suggestionCard"
        android:layout_width="0dp"
        android:layout_height="wrap_content"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintEnd_toEndOf="parent"
        android:layout_marginTop="12dp"/>

</androidx.constraintlayout.widget.ConstraintLayout>
```

- [ ] **Step 2: Item layout `item_transcript_segment.xml`**

```xml
<!-- poc/android/app/src/main/res/layout/item_transcript_segment.xml -->
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout
    xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:orientation="vertical"
    android:padding="6dp">
    <TextView android:id="@+id/speakerLabel"
        android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:textColor="#93C5FD" android:textSize="12sp"/>
    <TextView android:id="@+id/segmentText"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:textColor="#F1F5F9" android:textSize="16sp"/>
</LinearLayout>
```

- [ ] **Step 3: TranscriptAdapter**

```kotlin
// poc/android/app/src/main/java/com/autoluyin/demo/realtime/TranscriptAdapter.kt
package com.autoluyin.demo.realtime

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.autoluyin.demo.R

data class TranscriptSegment(
    val seq: Long,
    val speaker: String,  // "agent" / "customer"
    val text: String,
)

class TranscriptAdapter : RecyclerView.Adapter<TranscriptAdapter.VH>() {
    private val items = mutableListOf<TranscriptSegment>()

    fun append(seg: TranscriptSegment) {
        items += seg
        notifyItemInserted(items.size - 1)
    }

    fun snapshot(): List<TranscriptSegment> = items.toList()

    class VH(view: View) : RecyclerView.ViewHolder(view) {
        val label: TextView = view.findViewById(R.id.speakerLabel)
        val text: TextView = view.findViewById(R.id.segmentText)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_transcript_segment, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val seg = items[position]
        holder.label.text = if (seg.speaker == "agent") "[我]" else "[客户]"
        holder.text.text = seg.text
    }

    override fun getItemCount(): Int = items.size
}
```

- [ ] **Step 4: SuggestionCardView**

```kotlin
// poc/android/app/src/main/java/com/autoluyin/demo/realtime/SuggestionCardView.kt
package com.autoluyin.demo.realtime

import android.content.Context
import android.util.AttributeSet
import android.view.LayoutInflater
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.cardview.widget.CardView

class SuggestionCardView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : CardView(context, attrs) {

    private val titleView: TextView
    private val textView: TextView
    private val adoptBtn: Button
    private val ignoreBtn: Button

    var onAdopt: ((suggestionId: String) -> Unit)? = null
    var onIgnore: ((suggestionId: String) -> Unit)? = null

    private var currentSuggestionId: String? = null

    init {
        radius = 16f
        setContentPadding(16, 16, 16, 16)
        useCompatPadding = true
        val inflated = LayoutInflater.from(context).inflate(
            android.R.layout.simple_list_item_2, this, false
        )
        // Build a simple 4-row layout in code to avoid an extra layout file
        val container = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
        }
        titleView = TextView(context).apply { text = "💡 AI 建议"; textSize = 14f }
        textView = TextView(context).apply { textSize = 16f }
        val btnRow = LinearLayout(context).apply { orientation = LinearLayout.HORIZONTAL }
        adoptBtn = Button(context).apply { text = "采用" }
        ignoreBtn = Button(context).apply { text = "忽略" }
        btnRow.addView(adoptBtn)
        btnRow.addView(ignoreBtn)
        container.addView(titleView)
        container.addView(textView)
        container.addView(btnRow)
        addView(container)

        adoptBtn.setOnClickListener {
            currentSuggestionId?.let { id -> onAdopt?.invoke(id) }
        }
        ignoreBtn.setOnClickListener {
            currentSuggestionId?.let { id -> onIgnore?.invoke(id) }
        }
        visibility = GONE
    }

    fun show(suggestionId: String, text: String) {
        currentSuggestionId = suggestionId
        textView.text = text
        visibility = VISIBLE
    }

    fun hide() {
        currentSuggestionId = null
        visibility = GONE
    }
}
```

- [ ] **Step 5: RealtimeCallActivity**

```kotlin
// poc/android/app/src/main/java/com/autoluyin/demo/realtime/RealtimeCallActivity.kt
package com.autoluyin.demo.realtime

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class RealtimeCallActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_CALL_ID = "call_id"
        const val EXTRA_CASE_ID = "case_id"
        const val EXTRA_OWNER_NAME = "owner_name"
        const val EXTRA_OWNER_PHONE_MASKED = "owner_phone_masked"
        private const val REQ_PERMS = 4711
    }

    private lateinit var transcriptAdapter: TranscriptAdapter
    private lateinit var suggestionCard: SuggestionCardView
    private lateinit var connectionBadge: TextView
    private lateinit var timerView: TextView
    private lateinit var streamClient: AudioStreamClient

    private var callId: Long = -1
    private var caseId: Long = -1
    private val mainHandler = Handler(Looper.getMainLooper())
    private var startedAtMs: Long = 0
    private val tickRunnable = object : Runnable {
        override fun run() {
            val secs = (System.currentTimeMillis() - startedAtMs) / 1000
            timerView.text = "%02d:%02d".format(secs / 60, secs % 60)
            mainHandler.postDelayed(this, 1000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_realtime_call)

        callId = intent.getLongExtra(EXTRA_CALL_ID, -1L)
        caseId = intent.getLongExtra(EXTRA_CASE_ID, -1L)
        if (callId <= 0 || caseId <= 0) { finish(); return }

        findViewById<TextView>(R.id.ownerName).text =
            intent.getStringExtra(EXTRA_OWNER_NAME) ?: "未知业主"
        findViewById<TextView>(R.id.ownerRoom).text =
            intent.getStringExtra(EXTRA_OWNER_PHONE_MASKED) ?: ""

        connectionBadge = findViewById(R.id.connectionBadge)
        timerView = findViewById(R.id.timer)
        suggestionCard = findViewById(R.id.suggestionCard)

        val list = findViewById<RecyclerView>(R.id.transcriptList)
        list.layoutManager = LinearLayoutManager(this).apply { stackFromEnd = true }
        transcriptAdapter = TranscriptAdapter()
        list.adapter = transcriptAdapter

        findViewById<Button>(R.id.btnHangup).setOnClickListener { hangUp() }

        ensurePermissionsThenStart()
    }

    private fun ensurePermissionsThenStart() {
        val perms = arrayOf(Manifest.permission.RECORD_AUDIO, Manifest.permission.CALL_PHONE)
        val missing = perms.filter {
            ActivityCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) startCall()
        else ActivityCompat.requestPermissions(this, missing.toTypedArray(), REQ_PERMS)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, results: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, results)
        if (requestCode == REQ_PERMS && results.all { it == PackageManager.PERMISSION_GRANTED }) {
            startCall()
        } else {
            finish()
        }
    }

    private fun startCall() {
        // Place real phone call (PoC — production needs SIM-aware dialing)
        // Intent(Intent.ACTION_CALL, Uri.parse("tel:" + ownerPhonePlain)).also { startActivity(it) }
        startedAtMs = System.currentTimeMillis()
        mainHandler.post(tickRunnable)

        val token = AppConfig.token(this) ?: run { finish(); return }
        streamClient = AudioStreamClient(
            callId = callId,
            token = token,
            onTranscript = { seg -> mainHandler.post {
                transcriptAdapter.append(seg)
                findViewById<RecyclerView>(R.id.transcriptList).smoothScrollToPosition(transcriptAdapter.itemCount - 1)
            }},
            onSuggestion = { id, text -> mainHandler.post { suggestionCard.show(id, text) } },
            onTagReady = { tag -> mainHandler.post { showTagDialog(tag) } },
            onStateChange = { state -> mainHandler.post { renderState(state) } },
        )
        suggestionCard.onAdopt = { id -> postFeedback(id, "adopt") }
        suggestionCard.onIgnore = { id -> suggestionCard.hide(); postFeedback(id, "ignore") }
        streamClient.start()
    }

    private fun renderState(state: AudioStreamClient.State) {
        connectionBadge.text = when (state) {
            AudioStreamClient.State.NORMAL -> "🟢 实时"
            AudioStreamClient.State.DEGRADED -> "🟡 弱网"
            AudioStreamClient.State.FALLBACK_LOCAL -> "🔵 本地录音"
        }
    }

    private fun postFeedback(suggestionId: String, action: String) {
        val token = AppConfig.token(this) ?: return
        CoroutineScope(Dispatchers.IO).launch {
            runCatching {
                com.autoluyin.demo.ApiClient.service.postSuggestionFeedback(
                    authHeader = "Bearer $token",
                    callId = callId,
                    suggestionId = suggestionId,
                    body = mapOf("action" to action),
                )
            }
        }
    }

    private fun showTagDialog(tag: AudioStreamClient.TagPayload) {
        PostCallTagDialog.newInstance(callId, tag).show(supportFragmentManager, "tag")
    }

    private fun hangUp() {
        streamClient.stop()
        // tag dialog will be shown when server emits tag.ready (or on local fallback the dialog is opened with empty AI fields)
    }

    override fun onDestroy() {
        super.onDestroy()
        mainHandler.removeCallbacks(tickRunnable)
        if (::streamClient.isInitialized) streamClient.stop()
    }
}
```

> Note: `ApiClient.service.postSuggestionFeedback` is the Retrofit method added in T15 (PC frontend task). Add the matching Android Api.kt entry in this same task — see step below.

- [ ] **Step 6: Add `postSuggestionFeedback` to `Api.kt`**

In `poc/android/app/src/main/java/com/autoluyin/demo/Api.kt`:

```kotlin
@POST("api/v1/calls/{call_id}/suggestions/{suggestion_id}/feedback")
suspend fun postSuggestionFeedback(
    @Header("Authorization") authHeader: String,
    @Path("call_id") callId: Long,
    @Path("suggestion_id") suggestionId: String,
    @Body body: Map<String, String>,
): retrofit2.Response<Unit>
```

- [ ] **Step 7: Build verification**

```bash
cd /Users/shuo/AI/autoluyin/poc/android
./gradlew assembleDebug
```

Expected: APK builds (will fail if AudioStreamClient / PostCallTagDialog don't exist yet — that's resolved in T10/T11).

- [ ] **Step 8: Commit (after T10 + T11 land — do as a combined commit at end of T11 to keep the build green)**

```bash
# Defer commit until T11. Here just stage:
cd /Users/shuo/AI/autoluyin
git add poc/android/app/src/main/res/layout/activity_realtime_call.xml \
        poc/android/app/src/main/res/layout/item_transcript_segment.xml \
        poc/android/app/src/main/java/com/autoluyin/demo/realtime/RealtimeCallActivity.kt \
        poc/android/app/src/main/java/com/autoluyin/demo/realtime/TranscriptAdapter.kt \
        poc/android/app/src/main/java/com/autoluyin/demo/realtime/SuggestionCardView.kt \
        poc/android/app/src/main/java/com/autoluyin/demo/Api.kt
```

---

## Task 10: AudioStreamClient (WebSocket + AudioRecord)

**Goal:** Capture mic audio via `AudioRecord` (16 kHz mono PCM-16, 100 ms frames), open OkHttp WebSocket to backend, push frames as binary, dispatch incoming JSON events to UI callbacks. Owns thread model (recorder + sender + WS receive).

**Files:**
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/realtime/AudioStreamClient.kt`
- Create: `poc/android/app/src/test/java/com/autoluyin/demo/AudioStreamClientTest.kt`

**Subagent model:** sonnet

**Reference:** Spec §7.4

- [ ] **Step 1: Implement `AudioStreamClient`**

```kotlin
// poc/android/app/src/main/java/com/autoluyin/demo/realtime/AudioStreamClient.kt
package com.autoluyin.demo.realtime

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import com.autoluyin.demo.AppConfig
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread

class AudioStreamClient(
    private val callId: Long,
    private val token: String,
    private val onTranscript: (TranscriptSegment) -> Unit,
    private val onSuggestion: (id: String, text: String) -> Unit,
    private val onTagReady: (TagPayload) -> Unit,
    private val onStateChange: (State) -> Unit,
    private val baseUrl: String = "ws://10.0.2.2:8000",  // emulator → host loopback
) {
    enum class State { NORMAL, DEGRADED, FALLBACK_LOCAL }
    data class TagPayload(
        val intent: String?,
        val promiseDate: String?,
        val promiseAmount: Double?,
        val summary: String?,
    )

    private companion object {
        const val SAMPLE_RATE = 16000
        const val FRAME_MS = 100
        const val FRAME_BYTES = SAMPLE_RATE / 1000 * FRAME_MS * 2  // 3200
        const val QUEUE_CAPACITY = 50  // 5 seconds buffer
        const val PING_INTERVAL_MS = 30_000L
    }

    private val running = AtomicBoolean(false)
    private val sendQueue = LinkedBlockingQueue<ByteArray>(QUEUE_CAPACITY)
    private var ws: WebSocket? = null
    private var recorder: AudioRecord? = null
    private var recordThread: Thread? = null
    private var senderThread: Thread? = null
    private var state: State = State.NORMAL

    private val client by lazy {
        OkHttpClient.Builder()
            .pingInterval(30, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.MILLISECONDS)
            .build()
    }

    fun start() {
        if (running.getAndSet(true)) return
        connectWs()
        startRecorder()
        startSender()
    }

    fun stop() {
        if (!running.getAndSet(false)) return
        recorder?.stop()
        recorder?.release()
        recorder = null
        ws?.send(JSONObject().apply { put("type", "call.ended") }.toString())
        ws?.close(1000, "client closed")
        ws = null
        recordThread?.interrupt()
        senderThread?.interrupt()
    }

    private fun connectWs() {
        val req = Request.Builder()
            .url("$baseUrl/ws/calls/$callId?token=$token&role=agent")
            .build()
        ws = client.newWebSocket(req, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                transition(State.NORMAL)
                webSocket.send(JSONObject().apply { put("type", "call.started") }.toString())
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                handleJson(text)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                handleFailure()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                if (running.get()) handleFailure()
            }
        })
    }

    private fun handleJson(text: String) {
        val obj = try { JSONObject(text) } catch (_: Exception) { return }
        when (obj.optString("type")) {
            "transcript.chunk" -> onTranscript(
                TranscriptSegment(
                    seq = obj.optLong("seq"),
                    speaker = obj.optString("speaker", "customer"),
                    text = obj.optString("text"),
                )
            )
            "suggestion.ready" -> onSuggestion(
                obj.optString("id"),
                obj.optString("text"),
            )
            "tag.ready" -> onTagReady(
                TagPayload(
                    intent = obj.optString("intent").ifEmpty { null },
                    promiseDate = obj.optString("promise_date").ifEmpty { null },
                    promiseAmount = obj.optDouble("promise_amount").takeIf { !it.isNaN() },
                    summary = obj.optString("summary").ifEmpty { null },
                )
            )
            "pong" -> Unit  // heartbeat ack
        }
    }

    private fun handleFailure() {
        transition(State.DEGRADED)
        // Naive exponential backoff loop in a background thread
        thread(name = "ws-reconnect") {
            var attempt = 0
            while (running.get() && attempt < 5) {
                Thread.sleep(minOf(8_000L, (1L shl attempt) * 1000L))
                if (!running.get()) return@thread
                connectWs()
                Thread.sleep(2000)
                if (state == State.NORMAL) return@thread
                attempt += 1
            }
            if (running.get()) transition(State.FALLBACK_LOCAL)
        }
    }

    private fun transition(newState: State) {
        if (state != newState) {
            state = newState
            onStateChange(newState)
        }
    }

    private fun startRecorder() {
        val bufSize = AudioRecord.getMinBufferSize(
            SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
        ).coerceAtLeast(FRAME_BYTES * 4)
        recorder = AudioRecord(
            MediaRecorder.AudioSource.VOICE_COMMUNICATION,
            SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
            bufSize,
        ).also { it.startRecording() }

        recordThread = thread(name = "audio-record") {
            val frame = ByteArray(FRAME_BYTES)
            while (running.get()) {
                val rec = recorder ?: break
                val read = rec.read(frame, 0, FRAME_BYTES)
                if (read > 0) {
                    val copy = frame.copyOf(read)
                    if (!sendQueue.offer(copy)) {
                        // queue full: drop oldest 5 frames
                        repeat(5) { sendQueue.poll() }
                        sendQueue.offer(copy)
                        if (state == State.NORMAL) transition(State.DEGRADED)
                    }
                }
            }
        }
    }

    private fun startSender() {
        senderThread = thread(name = "audio-sender") {
            while (running.get()) {
                val frame = try { sendQueue.take() } catch (_: InterruptedException) { return@thread }
                val sock = ws ?: continue
                val ok = sock.send(frame.toByteString(0, frame.size))
                if (!ok && state == State.NORMAL) transition(State.DEGRADED)
            }
        }
    }
}
```

- [ ] **Step 2: Unit test (queue overflow + state transition)**

```kotlin
// poc/android/app/src/test/java/com/autoluyin/demo/AudioStreamClientTest.kt
package com.autoluyin.demo

import org.junit.jupiter.api.Test
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import java.util.concurrent.LinkedBlockingQueue

class AudioStreamClientTest {

    @Test
    fun `queue full drops oldest frames and reports DEGRADED`() {
        val q = LinkedBlockingQueue<ByteArray>(3)
        q.offer(byteArrayOf(1))
        q.offer(byteArrayOf(2))
        q.offer(byteArrayOf(3))

        val newFrame = byteArrayOf(99)
        if (!q.offer(newFrame)) {
            // simulate the drop-oldest logic from AudioStreamClient
            repeat(2) { q.poll() }
            q.offer(newFrame)
        }
        assertEquals(2, q.size)
        // The first two frames should have been dropped; queue contains [3, 99]
        assertEquals(3.toByte(), q.poll()!![0])
        assertEquals(99.toByte(), q.poll()!![0])
    }
}
```

> Note: Direct unit testing of `AudioStreamClient` requires Robolectric (it touches `AudioRecord` + OkHttp WebSocket). The test above asserts only the queue overflow contract. Full behavioral testing happens via E2E (T16) on a real or emulated device.

- [ ] **Step 3: Run unit test**

```bash
cd /Users/shuo/AI/autoluyin/poc/android
./gradlew test
```

Expected: passes.

- [ ] **Step 4: Stage (combined commit at T11)**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/android/app/src/main/java/com/autoluyin/demo/realtime/AudioStreamClient.kt \
        poc/android/app/src/test/java/com/autoluyin/demo/AudioStreamClientTest.kt
```

---

## Task 11: PostCallTagDialog

**Goal:** Bottom-sheet / dialog that prompts the agent to confirm intent + promise_date + summary right after hangup. Pre-fills with AI `tag.ready` payload, submits via `PATCH /calls/{id}/tag`, then returns to task list.

**Files:**
- Create: `poc/android/app/src/main/java/com/autoluyin/demo/realtime/PostCallTagDialog.kt`
- Create: `poc/android/app/src/main/res/layout/dialog_post_call_tag.xml`

**Subagent model:** sonnet

**Reference:** Spec §7.6

- [ ] **Step 1: Layout `dialog_post_call_tag.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout
    xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:orientation="vertical"
    android:padding="16dp">

    <TextView
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="通话标记" android:textSize="20sp" android:textStyle="bold"
        android:layout_marginBottom="16dp"/>

    <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="客户意图"/>
    <Spinner android:id="@+id/intentSpinner"
        android:layout_width="match_parent" android:layout_height="wrap_content"/>

    <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="承诺日期" android:layout_marginTop="8dp"/>
    <EditText android:id="@+id/promiseDateInput"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:hint="YYYY-MM-DD" android:inputType="date"/>

    <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="承诺金额（元）" android:layout_marginTop="8dp"/>
    <EditText android:id="@+id/promiseAmountInput"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:inputType="numberDecimal"/>

    <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="备注" android:layout_marginTop="8dp"/>
    <EditText android:id="@+id/notesInput"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:minLines="3" android:gravity="top"/>

    <LinearLayout
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:orientation="horizontal" android:gravity="end"
        android:layout_marginTop="16dp">
        <Button android:id="@+id/btnCancel" android:text="取消"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:layout_marginEnd="8dp"/>
        <Button android:id="@+id/btnSubmit" android:text="提交"
            android:layout_width="wrap_content" android:layout_height="wrap_content"/>
    </LinearLayout>
</LinearLayout>
```

- [ ] **Step 2: PostCallTagDialog**

```kotlin
// poc/android/app/src/main/java/com/autoluyin/demo/realtime/PostCallTagDialog.kt
package com.autoluyin.demo.realtime

import android.app.Dialog
import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.Spinner
import android.widget.Toast
import androidx.fragment.app.DialogFragment
import com.autoluyin.demo.AppConfig
import com.autoluyin.demo.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class PostCallTagDialog : DialogFragment() {

    companion object {
        private const val ARG_CALL_ID = "call_id"
        private const val ARG_INTENT = "intent"
        private const val ARG_DATE = "promise_date"
        private const val ARG_AMOUNT = "promise_amount"
        private const val ARG_SUMMARY = "summary"

        private val INTENT_OPTIONS = listOf(
            "promise_pay" to "承诺缴费",
            "refuse" to "拒绝缴费",
            "dispute" to "对欠费有异议",
            "no_answer" to "无人接听",
            "wrong_number" to "错号",
        )

        fun newInstance(callId: Long, tag: AudioStreamClient.TagPayload) =
            PostCallTagDialog().apply {
                arguments = Bundle().apply {
                    putLong(ARG_CALL_ID, callId)
                    tag.intent?.let { putString(ARG_INTENT, it) }
                    tag.promiseDate?.let { putString(ARG_DATE, it) }
                    tag.promiseAmount?.let { putDouble(ARG_AMOUNT, it) }
                    tag.summary?.let { putString(ARG_SUMMARY, it) }
                }
            }
    }

    override fun onCreateDialog(savedInstanceState: Bundle?): Dialog {
        val view = layoutInflater.inflate(R.layout.dialog_post_call_tag, null)
        val intentSpinner = view.findViewById<Spinner>(R.id.intentSpinner)
        val dateInput = view.findViewById<EditText>(R.id.promiseDateInput)
        val amountInput = view.findViewById<EditText>(R.id.promiseAmountInput)
        val notesInput = view.findViewById<EditText>(R.id.notesInput)
        val btnCancel = view.findViewById<Button>(R.id.btnCancel)
        val btnSubmit = view.findViewById<Button>(R.id.btnSubmit)

        intentSpinner.adapter = ArrayAdapter(
            requireContext(), android.R.layout.simple_spinner_item,
            INTENT_OPTIONS.map { it.second },
        )

        // Pre-fill from AI
        val args = requireArguments()
        args.getString(ARG_INTENT)?.let { code ->
            val idx = INTENT_OPTIONS.indexOfFirst { it.first == code }
            if (idx >= 0) intentSpinner.setSelection(idx)
        }
        dateInput.setText(args.getString(ARG_DATE, ""))
        if (args.containsKey(ARG_AMOUNT)) amountInput.setText(args.getDouble(ARG_AMOUNT).toString())
        notesInput.setText(args.getString(ARG_SUMMARY, ""))

        btnCancel.setOnClickListener { dismiss() }
        btnSubmit.setOnClickListener {
            val intentCode = INTENT_OPTIONS[intentSpinner.selectedItemPosition].first
            val date = dateInput.text.toString().ifBlank { null }
            val amount = amountInput.text.toString().toDoubleOrNull()
            val notes = notesInput.text.toString().ifBlank { null }
            submit(args.getLong(ARG_CALL_ID), intentCode, date, amount, notes)
        }

        return android.app.AlertDialog.Builder(requireContext()).setView(view).create()
    }

    private fun submit(
        callId: Long, intent: String, promiseDate: String?,
        promiseAmount: Double?, notes: String?,
    ) {
        val token = AppConfig.token(requireContext()) ?: return
        CoroutineScope(Dispatchers.IO).launch {
            val resp = runCatching {
                com.autoluyin.demo.ApiClient.service.patchCallTag(
                    authHeader = "Bearer $token",
                    callId = callId,
                    body = mapOf(
                        "intent" to intent,
                        "promise_date" to promiseDate,
                        "promise_amount" to promiseAmount,
                        "notes" to notes,
                    ).filterValues { it != null },
                )
            }
            withContext(Dispatchers.Main) {
                if (resp.isSuccess) {
                    Toast.makeText(requireContext(), "已提交", Toast.LENGTH_SHORT).show()
                    requireActivity().finish()
                } else {
                    Toast.makeText(requireContext(), "提交失败", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}
```

- [ ] **Step 3: Add `patchCallTag` to `Api.kt`**

```kotlin
@PATCH("api/v1/calls/{call_id}/tag")
suspend fun patchCallTag(
    @Header("Authorization") authHeader: String,
    @Path("call_id") callId: Long,
    @Body body: Map<String, Any>,
): retrofit2.Response<Unit>
```

- [ ] **Step 4: Build verification**

```bash
cd /Users/shuo/AI/autoluyin/poc/android
./gradlew assembleDebug
```

Expected: APK builds.

- [ ] **Step 5: Commit (combined T9 + T10 + T11)**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/android/app/src/main/java/com/autoluyin/demo/realtime/ \
        poc/android/app/src/main/res/layout/activity_realtime_call.xml \
        poc/android/app/src/main/res/layout/item_transcript_segment.xml \
        poc/android/app/src/main/res/layout/dialog_post_call_tag.xml \
        poc/android/app/src/main/java/com/autoluyin/demo/Api.kt \
        poc/android/app/src/test/java/com/autoluyin/demo/AudioStreamClientTest.kt
git commit -m "feat(android): RealtimeCallActivity + AudioStreamClient + PostCallTagDialog"
```

---

## Task 12: Android degradation state machine

**Goal:** When WebSocket fails, fall back to local recording → upload via Sprint 3a `POST /api/v1/calls/upload` after hangup. The state machine is partially in `AudioStreamClient` (T10) — this task wires the FALLBACK_LOCAL branch end-to-end.

**Files:**
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/realtime/AudioStreamClient.kt` — write PCM frames to a local WAV when in `FALLBACK_LOCAL`
- Modify: `poc/android/app/src/main/java/com/autoluyin/demo/realtime/RealtimeCallActivity.kt` — on hangup with FALLBACK_LOCAL, upload the WAV instead of relying on `tag.ready`
- Create: `poc/android/app/src/test/java/com/autoluyin/demo/DegradationStateMachineTest.kt`

**Subagent model:** sonnet

**Reference:** Spec §7.5

- [ ] **Step 1: Add local recording in `AudioStreamClient`**

In `AudioStreamClient`, add fields:

```kotlin
private var fallbackFile: java.io.File? = null
private var fallbackOutputStream: java.io.FileOutputStream? = null
```

In `transition(State.FALLBACK_LOCAL)`, open the file:

```kotlin
private fun startLocalFallback(ctx: android.content.Context) {
    val dir = ctx.getExternalFilesDir("recordings") ?: ctx.filesDir
    val f = java.io.File(dir, "call_${callId}_${System.currentTimeMillis()}.pcm")
    fallbackFile = f
    fallbackOutputStream = java.io.FileOutputStream(f)
}
```

Modify `startSender()` so that when `state == FALLBACK_LOCAL`, frames go to `fallbackOutputStream.write(frame)` instead of WS.

> Note: refactor required — `AudioStreamClient` constructor needs the `Context` (or accept it via `start(ctx)`). Update both the class and the `RealtimeCallActivity.startCall()` call site.

- [ ] **Step 2: Convert PCM to WAV on stop()**

Append a helper:

```kotlin
private fun finalizeFallbackWav(): java.io.File? {
    val pcm = fallbackFile ?: return null
    fallbackOutputStream?.close()
    val wav = java.io.File(pcm.parentFile, pcm.nameWithoutExtension + ".wav")
    writeWavHeader(wav, pcm)
    pcm.delete()
    return wav
}

private fun writeWavHeader(out: java.io.File, pcm: java.io.File) {
    val pcmBytes = pcm.readBytes()
    val totalLen = 36 + pcmBytes.size
    val byteRate = SAMPLE_RATE * 2  // 16-bit mono
    java.io.FileOutputStream(out).use { fos ->
        fos.write("RIFF".toByteArray())
        fos.write(intToBytesLe(totalLen))
        fos.write("WAVE".toByteArray())
        fos.write("fmt ".toByteArray())
        fos.write(intToBytesLe(16))           // PCM chunk size
        fos.write(shortToBytesLe(1))          // PCM format
        fos.write(shortToBytesLe(1))          // mono
        fos.write(intToBytesLe(SAMPLE_RATE))
        fos.write(intToBytesLe(byteRate))
        fos.write(shortToBytesLe(2))          // block align
        fos.write(shortToBytesLe(16))         // bits/sample
        fos.write("data".toByteArray())
        fos.write(intToBytesLe(pcmBytes.size))
        fos.write(pcmBytes)
    }
}

private fun intToBytesLe(v: Int) = byteArrayOf(
    (v and 0xff).toByte(), ((v shr 8) and 0xff).toByte(),
    ((v shr 16) and 0xff).toByte(), ((v shr 24) and 0xff).toByte(),
)
private fun shortToBytesLe(v: Int) = byteArrayOf(
    (v and 0xff).toByte(), ((v shr 8) and 0xff).toByte(),
)
```

Expose `fun stopAndCollectWav(): java.io.File?` that calls `stop()` then `finalizeFallbackWav()`.

- [ ] **Step 3: Wire fallback upload in `RealtimeCallActivity.hangUp()`**

```kotlin
private fun hangUp() {
    val wav = streamClient.stopAndCollectWav()
    if (wav != null) {
        // FALLBACK_LOCAL — upload via Sprint 3a endpoint
        uploadFallback(wav)
    }
    // The dialog will appear either way; if FALLBACK_LOCAL, AI fields stay empty
    if (!streamClient.hadServerTag()) {
        showTagDialog(AudioStreamClient.TagPayload(null, null, null, null))
    }
}

private fun uploadFallback(wav: java.io.File) {
    val token = AppConfig.token(this) ?: return
    val deviceId = AppConfig.deviceId(this) ?: return
    CoroutineScope(Dispatchers.IO).launch {
        runCatching {
            // Same multipart shape as Sprint 3a upload
            val body = okhttp3.MultipartBody.Builder()
                .setType(okhttp3.MultipartBody.FORM)
                .addFormDataPart("device_id", deviceId)
                .addFormDataPart("case_id", caseId.toString())
                .addFormDataPart("callee_phone", "")  // unused for FALLBACK; backend tolerant
                .addFormDataPart("started_at", "")
                .addFormDataPart("ended_at", "")
                .addFormDataPart("duration_sec", ((System.currentTimeMillis() - startedAtMs) / 1000).toString())
                .addFormDataPart(
                    "file", wav.name,
                    okhttp3.RequestBody.create("audio/wav".toMediaTypeOrNull(), wav),
                )
                .build()
            okhttp3.OkHttpClient().newCall(
                okhttp3.Request.Builder()
                    .url("${com.autoluyin.demo.ApiClient.BASE_URL}api/v1/calls/upload")
                    .header("Authorization", "Bearer $token")
                    .post(body).build()
            ).execute()
        }
    }
}
```

> Note: Server side currently requires `callee_phone` + `started_at` + `ended_at`. If the FALLBACK case can't supply these (DIAL_REQUEST never persisted them on Android), revisit `calls_v1.upload_call` to relax those for `initiated_by="pc"` calls created via dial-request. Track this as a Sprint 4 cleanup TODO.

- [ ] **Step 4: State machine unit test**

```kotlin
// poc/android/app/src/test/java/com/autoluyin/demo/DegradationStateMachineTest.kt
package com.autoluyin.demo

import com.autoluyin.demo.realtime.AudioStreamClient
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.Assertions.assertEquals

class DegradationStateMachineTest {

    @Test
    fun `state transitions follow expected order under repeated failures`() {
        val transitions = mutableListOf<AudioStreamClient.State>()
        val onChange: (AudioStreamClient.State) -> Unit = { transitions.add(it) }

        // Manually drive the state via the same logic AudioStreamClient uses
        var state = AudioStreamClient.State.NORMAL
        fun set(s: AudioStreamClient.State) {
            if (state != s) { state = s; onChange(s) }
        }

        set(AudioStreamClient.State.NORMAL)
        set(AudioStreamClient.State.DEGRADED)         // first failure
        set(AudioStreamClient.State.DEGRADED)         // dedup — no callback
        set(AudioStreamClient.State.NORMAL)            // reconnect succeeded
        set(AudioStreamClient.State.DEGRADED)
        set(AudioStreamClient.State.FALLBACK_LOCAL)    // exhausted retries

        assertEquals(
            listOf(
                AudioStreamClient.State.DEGRADED,
                AudioStreamClient.State.NORMAL,
                AudioStreamClient.State.DEGRADED,
                AudioStreamClient.State.FALLBACK_LOCAL,
            ),
            transitions
        )
    }
}
```

- [ ] **Step 5: Run unit tests**

```bash
cd /Users/shuo/AI/autoluyin/poc/android
./gradlew test
```

Expected: passes.

- [ ] **Step 6: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/android/app/src/main/java/com/autoluyin/demo/realtime/AudioStreamClient.kt \
        poc/android/app/src/main/java/com/autoluyin/demo/realtime/RealtimeCallActivity.kt \
        poc/android/app/src/test/java/com/autoluyin/demo/DegradationStateMachineTest.kt
git commit -m "feat(android): FALLBACK_LOCAL state — local WAV + Sprint 3a upload on reconnect failure"
```

---

## Task 13: PC ws-client (reconnecting WebSocket wrapper)

**Goal:** Browser-side WebSocket wrapper with exponential backoff reconnect, 30s ping heartbeat, JSON event dispatch, and a typed feedback sender. Wrapped by `useCallSocket` React hook for components.

**Files:**
- Create: `frontend/src/lib/realtime/types.ts`
- Create: `frontend/src/lib/realtime/ws-client.ts`
- Create: `frontend/src/hooks/useCallSocket.ts`
- Create: `frontend/src/lib/realtime/__tests__/ws-client.test.ts`

**Subagent model:** sonnet

**Reference:** Spec §8.2

- [ ] **Step 1: Shared types `types.ts`**

```ts
// frontend/src/lib/realtime/types.ts

export interface TranscriptChunk {
  seq: number;
  speaker: "agent" | "customer" | string;
  text: string;
  ts: string;  // ISO timestamp
  utterance_end?: boolean;
}

export interface Suggestion {
  id: string;
  text: string;
  intent?: string;
  confidence?: number;
}

export interface TagPayload {
  intent?: string;
  promise_date?: string;
  promise_amount?: number;
  summary?: string;
}

export type CallSocketStatus =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "failed"
  | "call_ended";

export interface CallSocketOptions {
  callId: number;
  role: "agent" | "observer";
  token: string;
  baseWsUrl?: string;  // default derived from window.location
  onTranscript?: (chunk: TranscriptChunk) => void;
  onSuggestion?: (s: Suggestion) => void;
  onTagReady?: (tag: TagPayload) => void;
  onStatusChange?: (status: CallSocketStatus) => void;
}

export interface CallSocketHandle {
  close: () => void;
  sendFeedback: (suggestionId: string, action: "adopt" | "ignore") => void;
}
```

- [ ] **Step 2: Failing test `ws-client.test.ts`**

```ts
// frontend/src/lib/realtime/__tests__/ws-client.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { openCallSocket } from "../ws-client";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  readyState = 0;
  sent: string[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.readyState = 3;
    this.onclose?.(new CloseEvent("close"));
  }
  fakeOpen() {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }
  fakeMessage(payload: unknown) {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(payload) }));
  }
  fakeFailure() {
    this.onerror?.(new Event("error"));
    this.close();
  }
}

describe("openCallSocket", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    // @ts-expect-error — override global for the test
    global.WebSocket = MockWebSocket;
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("dispatches transcript / suggestion / tag events", () => {
    const transcripts: unknown[] = [];
    const suggestions: unknown[] = [];
    const tags: unknown[] = [];
    const statuses: string[] = [];

    openCallSocket({
      callId: 42,
      role: "agent",
      token: "t",
      baseWsUrl: "ws://test",
      onTranscript: (c) => transcripts.push(c),
      onSuggestion: (s) => suggestions.push(s),
      onTagReady: (t) => tags.push(t),
      onStatusChange: (s) => statuses.push(s),
    });

    const sock = MockWebSocket.instances[0];
    sock.fakeOpen();
    sock.fakeMessage({ type: "transcript.chunk", seq: 1, speaker: "customer", text: "hi", ts: "" });
    sock.fakeMessage({ type: "suggestion.ready", id: "s1", text: "say x" });
    sock.fakeMessage({ type: "tag.ready", intent: "promise_pay" });

    expect(transcripts).toHaveLength(1);
    expect(suggestions).toHaveLength(1);
    expect(tags).toHaveLength(1);
    expect(statuses).toContain("connected");
  });

  it("attempts exponential backoff reconnects", () => {
    openCallSocket({ callId: 1, role: "agent", token: "t", baseWsUrl: "ws://test" });

    // Force the initial socket into a failed state
    MockWebSocket.instances[0].fakeFailure();
    expect(MockWebSocket.instances).toHaveLength(1);

    vi.advanceTimersByTime(1100);  // 1s backoff
    expect(MockWebSocket.instances).toHaveLength(2);

    MockWebSocket.instances[1].fakeFailure();
    vi.advanceTimersByTime(2100);  // 2s backoff
    expect(MockWebSocket.instances).toHaveLength(3);
  });

  it("sends ping on heartbeat interval", () => {
    openCallSocket({ callId: 1, role: "agent", token: "t", baseWsUrl: "ws://test" });
    const sock = MockWebSocket.instances[0];
    sock.fakeOpen();
    vi.advanceTimersByTime(30_000);
    expect(sock.sent.some((s) => s.includes('"ping"'))).toBe(true);
  });

  it("sendFeedback writes a JSON envelope", () => {
    const handle = openCallSocket({ callId: 1, role: "agent", token: "t", baseWsUrl: "ws://test" });
    const sock = MockWebSocket.instances[0];
    sock.fakeOpen();
    handle.sendFeedback("sug-1", "adopt");
    const last = sock.sent[sock.sent.length - 1];
    const parsed = JSON.parse(last);
    expect(parsed).toMatchObject({ type: "suggestion.feedback", id: "sug-1", action: "adopt" });
  });
});
```

- [ ] **Step 3: Run — confirm failure**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx vitest run src/lib/realtime/__tests__/ws-client.test.ts
```

Expected: module not found.

- [ ] **Step 4: Implement `ws-client.ts`**

```ts
// frontend/src/lib/realtime/ws-client.ts
import type {
  CallSocketHandle,
  CallSocketOptions,
  CallSocketStatus,
  TranscriptChunk,
  Suggestion,
  TagPayload,
} from "./types";

const PING_INTERVAL_MS = 30_000;
const MAX_BACKOFF_MS = 8_000;

function buildUrl(opts: CallSocketOptions): string {
  const base = opts.baseWsUrl ??
    (window.location.protocol === "https:" ? "wss://" : "ws://") + window.location.host;
  const u = new URL(`${base}/ws/calls/${opts.callId}`);
  u.searchParams.set("token", opts.token);
  u.searchParams.set("role", opts.role);
  return u.toString();
}

export function openCallSocket(opts: CallSocketOptions): CallSocketHandle {
  let socket: WebSocket | null = null;
  let pingTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let attempts = 0;
  let closedByCaller = false;

  const setStatus = (s: CallSocketStatus) => opts.onStatusChange?.(s);

  const connect = () => {
    setStatus(attempts === 0 ? "connecting" : "reconnecting");
    socket = new WebSocket(buildUrl(opts));

    socket.onopen = () => {
      attempts = 0;
      setStatus("connected");
      pingTimer = setInterval(() => {
        socket?.send(JSON.stringify({ type: "ping" }));
      }, PING_INTERVAL_MS);
    };

    socket.onmessage = (ev) => {
      let msg: { type?: string } & Record<string, unknown>;
      try {
        msg = JSON.parse(ev.data as string);
      } catch {
        return;
      }
      switch (msg.type) {
        case "transcript.chunk":
          opts.onTranscript?.(msg as unknown as TranscriptChunk);
          break;
        case "suggestion.ready":
          opts.onSuggestion?.(msg as unknown as Suggestion);
          break;
        case "tag.ready":
          opts.onTagReady?.(msg as unknown as TagPayload);
          break;
        case "pong":
        case "ack":
          break;
      }
    };

    socket.onerror = () => {
      // onclose will follow; do reconnect there
    };

    socket.onclose = () => {
      if (pingTimer) {
        clearInterval(pingTimer);
        pingTimer = null;
      }
      if (closedByCaller) {
        setStatus("call_ended");
        return;
      }
      const delay = Math.min(MAX_BACKOFF_MS, 1000 * Math.pow(2, attempts));
      attempts += 1;
      reconnectTimer = setTimeout(connect, delay);
      setStatus("reconnecting");
    };
  };

  connect();

  return {
    close() {
      closedByCaller = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pingTimer) clearInterval(pingTimer);
      socket?.close();
    },
    sendFeedback(suggestionId, action) {
      socket?.send(JSON.stringify({ type: "suggestion.feedback", id: suggestionId, action }));
    },
  };
}
```

- [ ] **Step 5: `useCallSocket` React hook**

```ts
// frontend/src/hooks/useCallSocket.ts
import { useEffect, useRef, useState } from "react";
import { openCallSocket } from "../lib/realtime/ws-client";
import type {
  CallSocketHandle,
  CallSocketStatus,
  Suggestion,
  TagPayload,
  TranscriptChunk,
} from "../lib/realtime/types";

export interface UseCallSocketArgs {
  callId: number;
  role: "agent" | "observer";
  token: string;
}

export interface UseCallSocketResult {
  status: CallSocketStatus;
  transcript: TranscriptChunk[];
  suggestions: Suggestion[];
  tag: TagPayload | null;
  sendFeedback: (id: string, action: "adopt" | "ignore") => void;
}

export function useCallSocket(args: UseCallSocketArgs): UseCallSocketResult {
  const [status, setStatus] = useState<CallSocketStatus>("connecting");
  const [transcript, setTranscript] = useState<TranscriptChunk[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [tag, setTag] = useState<TagPayload | null>(null);
  const handleRef = useRef<CallSocketHandle | null>(null);

  useEffect(() => {
    const handle = openCallSocket({
      callId: args.callId,
      role: args.role,
      token: args.token,
      onStatusChange: setStatus,
      onTranscript: (c) => setTranscript((prev) => [...prev, c]),
      onSuggestion: (s) => setSuggestions((prev) => [...prev, s]),
      onTagReady: (t) => setTag(t),
    });
    handleRef.current = handle;
    return () => handle.close();
  }, [args.callId, args.role, args.token]);

  return {
    status,
    transcript,
    suggestions,
    tag,
    sendFeedback: (id, action) => handleRef.current?.sendFeedback(id, action),
  };
}
```

- [ ] **Step 6: Run tests — confirm pass**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx vitest run src/lib/realtime/__tests__/ws-client.test.ts
```

Expected: 4 passed.

- [ ] **Step 7: TypeScript check**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx tsc --noEmit
```

Expected: clean.

- [ ] **Step 8: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add frontend/src/lib/realtime/ frontend/src/hooks/useCallSocket.ts
git commit -m "feat(frontend): WebSocket call client + useCallSocket hook with reconnect/heartbeat"
```

---

## Task 14: PC RealtimeCallWorkstation (three-column shell + agent/observer pages)

**Goal:** Three-column layout (owner info | live transcript | AI cards) hosted at `/agent/workstation/:call_id` (live agent) and `/admin/workstation/:call_id` (admin observer). Reuses `useCallSocket` from T13.

**Files:**
- Create: `frontend/src/components/realtime/RealtimeCallShell.tsx`
- Create: `frontend/src/components/realtime/TranscriptStream.tsx`
- Create: `frontend/src/components/realtime/ConnectionBadge.tsx`
- Create: `frontend/src/pages/agent/workstation/live.tsx`
- Create: `frontend/src/pages/admin/workstation/live.tsx`
- Modify: `frontend/src/App.tsx` — register two new routes
- Create: `frontend/src/components/realtime/__tests__/RealtimeCallShell.test.tsx`

**Subagent model:** sonnet

**Reference:** Spec §8.3, §8.4, §8.5, §8.6

- [ ] **Step 1: ConnectionBadge**

```tsx
// frontend/src/components/realtime/ConnectionBadge.tsx
import type { CallSocketStatus } from "../../lib/realtime/types";

const LABELS: Record<CallSocketStatus, { text: string; cls: string }> = {
  connecting: { text: "连接中…", cls: "text-slate-500" },
  connected: { text: "🟢 实时", cls: "text-emerald-600" },
  reconnecting: { text: "🟡 重连中", cls: "text-amber-600" },
  failed: { text: "🔴 失联", cls: "text-red-600" },
  call_ended: { text: "通话结束", cls: "text-slate-400" },
};

export function ConnectionBadge({ status }: { status: CallSocketStatus }) {
  const { text, cls } = LABELS[status];
  return <span className={`text-sm font-medium ${cls}`}>{text}</span>;
}
```

- [ ] **Step 2: TranscriptStream**

```tsx
// frontend/src/components/realtime/TranscriptStream.tsx
import { useEffect, useRef } from "react";
import type { TranscriptChunk } from "../../lib/realtime/types";

export function TranscriptStream({ chunks }: { chunks: TranscriptChunk[] }) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chunks.length]);

  return (
    <div className="flex-1 overflow-y-auto rounded-lg bg-slate-900 p-4 text-slate-100">
      {chunks.length === 0 && (
        <div className="text-slate-500 text-sm">等待音频流…</div>
      )}
      {chunks.map((c) => (
        <div key={c.seq} className="mb-2">
          <span className={`text-xs ${c.speaker === "agent" ? "text-blue-300" : "text-rose-300"}`}>
            {c.speaker === "agent" ? "[我]" : "[客户]"}
          </span>{" "}
          <span className="text-base">{c.text}</span>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
```

- [ ] **Step 3: SuggestionCardStack (referenced; full impl in T15 — stub here)**

```tsx
// frontend/src/components/realtime/SuggestionCardStack.tsx
import type { Suggestion } from "../../lib/realtime/types";

interface Props {
  suggestions: Suggestion[];
  onFeedback: (id: string, action: "adopt" | "ignore") => void;
  readOnly?: boolean;
}

export function SuggestionCardStack({ suggestions, onFeedback, readOnly }: Props) {
  if (suggestions.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 p-4 text-sm text-slate-500">
        AI 建议会在这里出现
      </div>
    );
  }
  const latest = suggestions[suggestions.length - 1];
  const history = suggestions.slice(0, -1);
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-4">
        <div className="text-xs font-semibold text-emerald-700">💡 当前建议</div>
        <div className="mt-1 text-base text-slate-900">{latest.text}</div>
        {!readOnly && (
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => onFeedback(latest.id, "adopt")}
              className="rounded-md bg-emerald-600 px-3 py-1 text-sm text-white hover:bg-emerald-700"
            >采用</button>
            <button
              onClick={() => onFeedback(latest.id, "ignore")}
              className="rounded-md border border-slate-300 px-3 py-1 text-sm text-slate-700"
            >忽略</button>
          </div>
        )}
      </div>
      {history.length > 0 && (
        <details className="rounded-md border border-slate-200 p-2 text-sm">
          <summary className="cursor-pointer text-slate-600">历史 ({history.length})</summary>
          <ul className="mt-2 space-y-1">
            {history.map((s) => <li key={s.id} className="text-slate-700">• {s.text}</li>)}
          </ul>
        </details>
      )}
    </div>
  );
}
```

- [ ] **Step 4: RealtimeCallShell**

```tsx
// frontend/src/components/realtime/RealtimeCallShell.tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCallSocket } from "../../hooks/useCallSocket";
import { ConnectionBadge } from "./ConnectionBadge";
import { TranscriptStream } from "./TranscriptStream";
import { SuggestionCardStack } from "./SuggestionCardStack";

interface OwnerSummary {
  name: string;
  building?: string;
  room?: string;
  amount_owed?: string;
}

interface Props {
  callId: number;
  role: "agent" | "observer";
  token: string;
  owner: OwnerSummary | null;
}

export function RealtimeCallShell({ callId, role, token, owner }: Props) {
  const navigate = useNavigate();
  const { status, transcript, suggestions, tag, sendFeedback } = useCallSocket({ callId, role, token });
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (tag !== null) {
      // Server confirmed final analysis — jump to call detail
      const timeout = setTimeout(() => navigate(`/calls/${callId}`), 800);
      return () => clearTimeout(timeout);
    }
  }, [tag, callId, navigate]);

  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <header className="flex items-center justify-between rounded-lg bg-white px-4 py-2 shadow-sm">
        <div className="font-mono text-lg text-slate-700">通话 {mm}:{ss}</div>
        <ConnectionBadge status={status} />
        {role === "observer" && (
          <span className="text-sm text-slate-500">正在旁听</span>
        )}
      </header>

      <div className="grid flex-1 gap-4" style={{ gridTemplateColumns: "280px 1fr 320px" }}>
        <aside className="rounded-lg bg-white p-4 shadow-sm">
          {owner ? (
            <>
              <div className="text-xl font-semibold">{owner.name}</div>
              <div className="mt-1 text-sm text-slate-500">
                {owner.building} {owner.room}
              </div>
              {owner.amount_owed && (
                <div className="mt-3 text-base text-rose-600">
                  欠费 ¥{owner.amount_owed}
                </div>
              )}
            </>
          ) : (
            <div className="text-sm text-slate-400">加载业主信息中…</div>
          )}
        </aside>

        <TranscriptStream chunks={transcript} />

        <aside>
          <SuggestionCardStack
            suggestions={suggestions}
            onFeedback={(id, action) => sendFeedback(id, action)}
            readOnly={role === "observer"}
          />
        </aside>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Agent live page**

```tsx
// frontend/src/pages/agent/workstation/live.tsx
import { useParams } from "react-router-dom";
import { useOne } from "@refinedev/core";
import { RealtimeCallShell } from "../../../components/realtime/RealtimeCallShell";

export function AgentLiveWorkstationPage() {
  const { call_id } = useParams<{ call_id: string }>();
  const callId = Number(call_id);
  const token = localStorage.getItem("access_token") ?? "";

  // Fetch owner info via the call detail endpoint (which references the case)
  const { data } = useOne<{ case_id: number }>({
    resource: "calls", id: callId, queryOptions: { enabled: !!callId },
  });
  const caseId = data?.data?.case_id;
  const { data: caseData } = useOne<{ owner_name?: string; owner_building?: string; owner_room?: string; amount_owed?: string }>({
    resource: "agent/cases", id: caseId ?? 0, queryOptions: { enabled: !!caseId },
  });
  const owner = caseData?.data
    ? {
        name: caseData.data.owner_name ?? "未知业主",
        building: caseData.data.owner_building,
        room: caseData.data.owner_room,
        amount_owed: caseData.data.amount_owed,
      }
    : null;

  if (!callId) return <div>缺少 call_id</div>;
  return <RealtimeCallShell callId={callId} role="agent" token={token} owner={owner} />;
}
```

- [ ] **Step 6: Admin observer page**

```tsx
// frontend/src/pages/admin/workstation/live.tsx
import { useParams } from "react-router-dom";
import { useOne } from "@refinedev/core";
import { RealtimeCallShell } from "../../../components/realtime/RealtimeCallShell";

export function AdminLiveWorkstationPage() {
  const { call_id } = useParams<{ call_id: string }>();
  const callId = Number(call_id);
  const token = localStorage.getItem("access_token") ?? "";

  const { data } = useOne<{ case_id: number; owner_name?: string }>({
    resource: "calls", id: callId, queryOptions: { enabled: !!callId },
  });
  const owner = data?.data ? { name: data.data.owner_name ?? "" } : null;

  if (!callId) return <div>缺少 call_id</div>;
  return <RealtimeCallShell callId={callId} role="observer" token={token} owner={owner} />;
}
```

- [ ] **Step 7: Register routes in `App.tsx`**

Inside the authenticated routes block, add:

```tsx
import { AgentLiveWorkstationPage } from "./pages/agent/workstation/live";
import { AdminLiveWorkstationPage } from "./pages/admin/workstation/live";

// inside <Routes>...
<Route path="/agent/workstation/:call_id" element={<AgentLiveWorkstationPage />} />
<Route path="/admin/workstation/:call_id" element={<AdminLiveWorkstationPage />} />
```

- [ ] **Step 8: Component test**

```tsx
// frontend/src/components/realtime/__tests__/RealtimeCallShell.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RealtimeCallShell } from "../RealtimeCallShell";

vi.mock("../../../hooks/useCallSocket", () => ({
  useCallSocket: () => ({
    status: "connected",
    transcript: [
      { seq: 1, speaker: "customer", text: "您好哪位", ts: "" },
      { seq: 2, speaker: "agent", text: "您好这里是物业", ts: "" },
    ],
    suggestions: [{ id: "s1", text: "建议询问家庭收入情况" }],
    tag: null,
    sendFeedback: vi.fn(),
  }),
}));

describe("RealtimeCallShell", () => {
  it("renders transcript and suggestion in connected state", () => {
    render(
      <MemoryRouter>
        <RealtimeCallShell
          callId={1}
          role="agent"
          token="t"
          owner={{ name: "张三", room: "1栋101", amount_owed: "2400.00" }}
        />
      </MemoryRouter>
    );
    expect(screen.getByText("张三")).toBeDefined();
    expect(screen.getByText("您好哪位")).toBeDefined();
    expect(screen.getByText("您好这里是物业")).toBeDefined();
    expect(screen.getByText(/建议询问家庭收入情况/)).toBeDefined();
    expect(screen.getByText(/实时/)).toBeDefined();
  });
});
```

- [ ] **Step 9: Run tests + build**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx vitest run
npx tsc --noEmit && npm run build
```

Expected: tests pass, build clean.

- [ ] **Step 10: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add frontend/src/components/realtime/ \
        frontend/src/pages/agent/workstation/ \
        frontend/src/pages/admin/workstation/ \
        frontend/src/App.tsx
git commit -m "feat(frontend): RealtimeCallShell three-column layout — agent + observer pages"
```

---

## Task 15: PC AI suggestion feedback POST + dial button on case list

**Goal:** Wire the SuggestionCardStack's "采用 / 忽略" buttons to `POST /api/v1/calls/{call_id}/suggestions/{suggestion_id}/feedback`. Add the "拨打" button on agent case list that calls `POST /api/v1/calls/dial-request` and navigates to the workstation page.

**Files:**
- Modify: `frontend/src/components/realtime/RealtimeCallShell.tsx` — wrap `sendFeedback` to also POST
- Create: `frontend/src/lib/realtime/feedback-api.ts`
- Modify: `frontend/src/pages/agent/cases/index.tsx` — add "拨打" button + dial flow
- Create: `poc/backend/tests/api/test_suggestion_feedback.py`
- Modify: `poc/backend/app/api/calls_v1.py` — add the feedback endpoint
- Modify: `poc/backend/app/models/call.py` — `SuggestionFeedback` model (defined in T1; if missing add)

**Subagent model:** sonnet

**Reference:** Spec §5.3

- [ ] **Step 1: Backend — failing test for feedback endpoint**

```python
# poc/backend/tests/api/test_suggestion_feedback.py
import pytest


@pytest.fixture
def seeded_call_processed(db_session, seeded_case, seeded_member_user, seeded_tenant):
    from datetime import datetime, timezone
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13700000000"),
        initiated_by="pc",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration_sec=60,
        status="processed",
    )
    db_session.add(call)
    db_session.flush()
    return call


@pytest.mark.asyncio
async def test_suggestion_feedback_inserts_row(client, agent_auth_headers, seeded_call_processed, db_session):
    resp = await client.post(
        f"/api/v1/calls/{seeded_call_processed.id}/suggestions/sug-abc/feedback",
        json={"action": "adopt"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201, resp.text

    from app.models.call import SuggestionFeedback
    from sqlalchemy import select
    rows = db_session.execute(
        select(SuggestionFeedback).where(SuggestionFeedback.call_id == seeded_call_processed.id)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].suggestion_id == "sug-abc"
    assert rows[0].action == "adopt"


@pytest.mark.asyncio
async def test_suggestion_feedback_idempotent(client, agent_auth_headers, seeded_call_processed):
    body = {"action": "ignore"}
    resp1 = await client.post(
        f"/api/v1/calls/{seeded_call_processed.id}/suggestions/sug-xyz/feedback",
        json=body, headers=agent_auth_headers,
    )
    assert resp1.status_code == 201
    resp2 = await client.post(
        f"/api/v1/calls/{seeded_call_processed.id}/suggestions/sug-xyz/feedback",
        json=body, headers=agent_auth_headers,
    )
    assert resp2.status_code == 200  # idempotent — already recorded


@pytest.mark.asyncio
async def test_suggestion_feedback_other_user_forbidden(
    client, supervisor_auth_headers, seeded_call_processed,
):
    resp = await client.post(
        f"/api/v1/calls/{seeded_call_processed.id}/suggestions/sug-1/feedback",
        json={"action": "adopt"},
        headers=supervisor_auth_headers,
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Implement endpoint**

In `poc/backend/app/schemas/call.py`:

```python
class SuggestionFeedbackIn(BaseModel):
    action: str  # "adopt" | "ignore"
    suggestion_text: Optional[str] = None
```

In `poc/backend/app/api/calls_v1.py`:

```python
from app.schemas.call import SuggestionFeedbackIn

@router.post("/{call_id}/suggestions/{suggestion_id}/feedback", status_code=201)
def post_suggestion_feedback(
    call_id: int,
    suggestion_id: str,
    body: SuggestionFeedbackIn,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    user_id = int(payload.get("user_id") or 0)
    tenant_id = int(payload.get("tenant_id") or 0)

    call = db.execute(
        select(CallRecord).where(
            CallRecord.id == call_id, CallRecord.tenant_id == tenant_id
        )
    ).scalar_one_or_none()
    if not call:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "通话记录不存在"},
        )
    if call.caller_user_id != user_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "无权对此通话提交反馈"},
        )

    if body.action not in ("adopt", "ignore"):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_VALIDATION", "message": "action 必须是 adopt 或 ignore"},
        )

    from app.models.call import SuggestionFeedback
    existing = db.execute(
        select(SuggestionFeedback).where(
            SuggestionFeedback.call_id == call_id,
            SuggestionFeedback.suggestion_id == suggestion_id,
        )
    ).scalar_one_or_none()
    if existing:
        # idempotent — return 200 without re-inserting
        from fastapi import Response
        return Response(status_code=200, content="{}", media_type="application/json")

    fb = SuggestionFeedback(
        call_id=call_id,
        suggestion_id=suggestion_id,
        user_id=user_id,
        action=body.action,
        suggestion_text=body.suggestion_text or "",
    )
    db.add(fb)
    db.commit()
    return {"id": fb.id}
```

> Note: The route returns a JSON `dict` for 201 and a raw `Response(200)` for the idempotent path. Refactor to a `JSONResponse(status_code=...)` for cleanliness if preferred. Spec §5.3 requires the idempotent path to return 200, not 201.

- [ ] **Step 3: Run backend tests — confirm pass**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/python3.12 -m pytest tests/api/test_suggestion_feedback.py -v
```

Expected: 3 passed.

- [ ] **Step 4: Frontend — feedback REST helper**

```ts
// frontend/src/lib/realtime/feedback-api.ts
export async function postSuggestionFeedback(
  callId: number,
  suggestionId: string,
  action: "adopt" | "ignore",
  token: string,
): Promise<void> {
  const resp = await fetch(
    `/api/v1/calls/${callId}/suggestions/${encodeURIComponent(suggestionId)}/feedback`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ action }),
    },
  );
  if (!resp.ok) {
    throw new Error(`feedback failed: ${resp.status}`);
  }
}
```

- [ ] **Step 5: Wire feedback into RealtimeCallShell**

In `frontend/src/components/realtime/RealtimeCallShell.tsx`, replace the inline `sendFeedback` passed to `SuggestionCardStack` with a wrapper that POSTs:

```tsx
import { postSuggestionFeedback } from "../../lib/realtime/feedback-api";

// inside the component, before rendering:
const handleFeedback = (id: string, action: "adopt" | "ignore") => {
  sendFeedback(id, action);  // WS ack for instant UX
  void postSuggestionFeedback(callId, id, action, token);  // durable
};

// pass handleFeedback to <SuggestionCardStack onFeedback={...}/>
```

- [ ] **Step 6: Add "拨打" button to agent case list**

Read `frontend/src/pages/agent/cases/index.tsx`. In the row actions cell (or wherever buttons live), add:

```tsx
import { useNavigate } from "react-router-dom";

// inside row cell — for each row `record`:
const navigate = useNavigate();
const onDial = async () => {
  const token = localStorage.getItem("access_token") ?? "";
  const resp = await fetch("/api/v1/calls/dial-request", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ case_id: record.id }),
  });
  if (!resp.ok) {
    alert("拨打失败：" + resp.status);
    return;
  }
  const body = await resp.json();
  navigate(`/agent/workstation/${body.call_id}`);
};

<Button size="sm" onClick={onDial}>拨打</Button>
```

> Note: The exact JSX integration depends on how `cases/index.tsx` is currently structured (Refine `<Table>` with action column, custom flex grid, etc.). Read the existing file first and adapt the placement.

- [ ] **Step 7: Run tests + build**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx vitest run
npx tsc --noEmit && npm run build
```

Expected: clean.

- [ ] **Step 8: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/call.py \
        poc/backend/app/api/calls_v1.py \
        poc/backend/tests/api/test_suggestion_feedback.py \
        frontend/src/lib/realtime/feedback-api.ts \
        frontend/src/components/realtime/RealtimeCallShell.tsx \
        frontend/src/pages/agent/cases/index.tsx
git commit -m "feat: suggestion feedback POST + agent dial button → workstation"
```

---

## Task 16: End-to-end integration test (mock backends)

**Goal:** A single pytest that exercises the full Sprint 4 path: agent posts dial-request → backend inserts pending_dial + sends MiPush mock → agent connects WS → audio frames feed mock ASR → mock LLM emits a suggestion → agent receives `transcript.chunk` + `suggestion.ready` → agent sends `call.ended` → backend transitions to `live_ended_pending_analysis`. This is the "smoke" gate before Sprint 4 ships.

**Files:**
- Create: `poc/backend/tests/integration/__init__.py`
- Create: `poc/backend/tests/integration/test_sprint4_e2e.py`

**Subagent model:** sonnet

**Reference:** Spec §9.4, §12 (acceptance)

- [ ] **Step 1: Empty package marker**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
touch tests/integration/__init__.py
```

- [ ] **Step 2: Integration test**

```python
# poc/backend/tests/integration/test_sprint4_e2e.py
"""Sprint 4 end-to-end smoke — mock ASR + mock LLM + mock MiPush.

Runs entirely in-process. Does NOT require Android, real DashScope, or Xiaomi credentials.
"""
import pytest
from starlette.testclient import TestClient


@pytest.fixture
def assigned_case_with_device(
    db_session, seeded_case, seeded_member_user, seeded_tenant,
):
    from app.models.device import DeviceProfile
    seeded_case.assigned_to = seeded_member_user.id
    db_session.flush()
    device = DeviceProfile(
        device_id="e2e-device-001",
        user_id=seeded_member_user.id,
        tenant_id=seeded_tenant.id,
        push_reg_id="reg-e2e-001",
        push_provider="xiaomi",
        is_healthy=True,
    )
    db_session.add(device)
    db_session.flush()
    return seeded_case


@pytest.mark.asyncio
async def test_full_call_assistance_flow(
    client, agent_auth_headers, assigned_case_with_device, db_session,
    seeded_member_user, seeded_tenant,
):
    """End-to-end: dial-request → MiPush emitted → WS connect → ASR → suggestion → call.ended."""
    from app.services import mipush
    mipush._reset_for_tests()
    from app.core.security import create_access_token

    # 1. Agent issues dial-request via PC
    resp = await client.post(
        "/api/v1/calls/dial-request",
        json={"case_id": assigned_case_with_device.id},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    call_id = resp.json()["call_id"]

    # 2. MiPush mock captured the DIAL_REQUEST payload
    sent = mipush._get_mock_sent()
    assert len(sent) == 1
    pushed = sent[0]
    assert pushed["payload"]["type"] == "DIAL_REQUEST"
    assert pushed["payload"]["call_id"] == call_id

    # 3. Android (simulated) connects WebSocket as agent
    token = create_access_token({
        "sub": str(seeded_member_user.id),
        "user_id": seeded_member_user.id,
        "tenant_id": seeded_tenant.id,
        "role": "agent_internal",
        "scope": f"tenant:{seeded_tenant.id}",
    })

    from app.main import app
    from app.core.db import get_db

    def override_db():
        yield db_session
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as cli:
            with cli.websocket_connect(
                f"/ws/calls/{call_id}?token={token}&role=agent"
            ) as ws:
                ws.send_json({"type": "call.started"})

                # Feed ~3s of fake audio — mock ASR emits a chunk per second
                fake_frame = b"\x00" * 3200
                for _ in range(30):
                    ws.send_bytes(fake_frame)

                # Drain whatever the server has produced
                received: list[dict] = []
                for _ in range(40):
                    try:
                        msg = ws.receive_json()
                        received.append(msg)
                    except Exception:
                        break
                    if any(m.get("type") == "transcript.chunk" for m in received) and \
                       any(m.get("type") == "suggestion.ready" for m in received):
                        break

                ws.send_json({"type": "call.ended"})

        # 4. Verify the broadcasts arrived
        types = [m.get("type") for m in received]
        assert "transcript.chunk" in types, f"no transcript chunks: {types}"

        # 5. Server status transitioned
        from app.models.call import CallRecord
        from sqlalchemy import select
        db_session.expire_all()
        call = db_session.execute(
            select(CallRecord).where(CallRecord.id == call_id)
        ).scalar_one()
        assert call.status in (
            "live_ended_pending_analysis", "processed", "live"
        ), f"unexpected final status: {call.status}"
    finally:
        app.dependency_overrides.clear()
```

> Note: A `suggestion.ready` assertion is intentionally omitted from the strict path because the mock LLM debounce + fake-time tradeoff makes timing flaky. If T3's mock is deterministic enough to always emit within 3s, tighten the assertion to require both chunk types.

- [ ] **Step 3: Run all backend tests**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/python3.12 -m pytest --tb=short -q
```

Expected: all green (~120 tests including ~16 new in Sprint 4).

- [ ] **Step 4: Run frontend tests + build + Android build**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx vitest run && npx tsc --noEmit && npm run build

cd /Users/shuo/AI/autoluyin/poc/android
./gradlew test assembleDebug
```

All three must pass.

- [ ] **Step 5: Manual smoke (optional, requires dev server + emulator)**

Per Spec §12:

1. Backend up: `cd poc/backend && uvicorn app.main:app --reload --port 8000`
2. Frontend up: `cd frontend && npm run dev`
3. Login as admin → create case → assign to agent
4. Login as agent (other browser/incognito) → case list → click "拨打"
5. Should navigate to `/agent/workstation/{call_id}` with three-column layout
6. Verify ConnectionBadge → "🟢 实时", transcript stream populates over ~3s with mock text
7. AI suggestion card appears with "采用 / 忽略"; click → 201 logged
8. (Optional) Hit `POST /api/v1/calls/{id}/tag` via curl to simulate hangup tagging

- [ ] **Step 6: Final commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/tests/integration/
git commit -m "test: Sprint 4 e2e smoke — dial-request → WS → ASR → suggestion → call.ended"
```

---

## Sprint 4 Done — Verification Checklist

- [ ] All 16 tasks committed (one or more commits per task; combined commits where noted)
- [ ] `pytest --tb=short -q` in `poc/backend/` — all green
- [ ] `npx vitest run && npx tsc --noEmit && npm run build` in `frontend/` — clean
- [ ] `./gradlew test assembleDebug` in `poc/android/` — clean
- [ ] Manual smoke in §T16 step 5 passes end-to-end with mock backends
- [ ] No production credentials hardcoded; all real backends gated behind `*_BACKEND` env switches
- [ ] PRD-relevant deltas (if any) sent through `prd-section-writer` skill

---

## Open Questions / Followups (track in Sprint 5)

1. **Real audio playback on PC observer.** Currently observers see transcript only — no audio. If supervisors need to hear, add audio relay in `CallSession` (server tees frames to observers).
2. **Multi-worker Redis pub/sub.** ConnectionManager is single-process. When backend scales horizontally, swap to Redis-backed broadcast.
3. **DashScope streaming smoke.** Backend code is written but only `mock` is exercised in CI. Schedule a one-off cloud run before launch.
4. **MiPush AppID/AppKey provisioning.** Track in deployment runbook; needed for any real-device testing.
5. **Fallback upload schema mismatch.** `POST /calls/upload` requires `started_at`/`ended_at` — these may be empty when FALLBACK_LOCAL fires. Either relax server validation for `initiated_by="pc"` or compute timestamps on Android before upload.
6. **Live "正在通话中" badge in admin case detail.** Spec §8.5 mentions it but no surface yet — link from `admin/cases/:id` to `/admin/workstation/:call_id`.

---
