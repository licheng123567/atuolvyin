# poc/backend/app/ws/call_session.py
from __future__ import annotations

import logging
from typing import Callable, Awaitable, Optional

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
        on_transcript_broadcast: Callable[[dict], Awaitable[None]],
        on_suggestion_broadcast: Callable[[dict], Awaitable[None]],
        on_tag_ready: Callable[[dict], Awaitable[None]],
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
                await self._on_suggestion(suggestion.to_message())

    async def _handle_error(self, exc: Exception) -> None:
        logger.error("ASR error call=%s: %s", self.call_id, exc)
