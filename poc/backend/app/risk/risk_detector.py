from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.risk.keyword_matcher import KeywordHit, get_matcher
from app.risk.risk_analyzer import analyze_risk_with_llm
from app.services.streaming_asr import TranscriptChunk


class RiskDetector:
    """Per-call risk coordinator.

    On each utterance_end TranscriptChunk:
    1. speaker == 'unknown' → skip
    2. Keyword match (sync) → emit keyword event immediately + schedule LLM confirmation
    3. Regardless of keyword hit, schedule LLM free-form scan (10s throttle)
    4. Dedup: same category within risk_dedup_window_sec suppressed
    """

    def __init__(
        self,
        call_id: int,
        tenant_id: int,
        on_event: Callable[[dict], Awaitable[None]],
    ) -> None:
        self.call_id = call_id
        self.tenant_id = tenant_id
        self._on_event = on_event
        # category -> last emitted timestamp
        self._last_emit: dict[str, float] = {}
        # Per-speaker free LLM throttle timestamp
        self._last_free_llm: dict[str, float] = {}

    async def on_utterance(self, chunk: TranscriptChunk, db: Session) -> None:
        if not chunk.utterance_end:
            return
        if chunk.speaker == "unknown":
            return

        matcher = get_matcher(tenant_id=self.tenant_id, speaker=chunk.speaker)
        await matcher.ensure_loaded(db=db)
        hits = matcher.match(chunk.text)

        if hits:
            # Emit keyword event immediately for the first (highest severity) hit
            primary = hits[0]
            risk_id = str(uuid.uuid4())
            if self._should_emit(primary.category):
                event = self._build_event(
                    risk_id=risk_id,
                    category=primary.category,
                    speaker=chunk.speaker,
                    level=primary.level,
                    trigger="keyword",
                    keyword=primary.keyword,
                    llm_confidence=None,
                    text=chunk.text,
                )
                await self._on_event(event)
                self._mark_emit(primary.category)
                        # Schedule LLM confirmation — emits upgraded keyword+llm event if confirmed
                asyncio.create_task(
                    self._llm_confirm(risk_id=risk_id, chunk=chunk, hint=primary)
                )

        else:
            # Free-form LLM scan (throttled)
            now = time.monotonic()
            last = self._last_free_llm.get(chunk.speaker, 0.0)
            if now - last >= settings.risk_llm_free_throttle_sec:
                self._last_free_llm[chunk.speaker] = now
                asyncio.create_task(
                    self._llm_free_scan(chunk=chunk)
                )

    async def _llm_confirm(
        self, risk_id: str, chunk: TranscriptChunk, hint: KeywordHit
    ) -> None:
        verdict = await analyze_risk_with_llm(
            transcript_text=chunk.text,
            speaker=chunk.speaker,
            keyword_hint=hint,
        )
        if not verdict.is_risk:
            # LLM says false positive — keep keyword-only event as-is, no upgrade
            return

        # LLM confirms → emit upgraded event with keyword+llm trigger so client can
        # escalate from dismissible banner to blocking modal.
        # NOTE: no dedup check here — this is an upgrade of an already-emitted keyword
        # event, not a new independent detection; dedup only blocks new keyword hits.
        event = self._build_event(
            risk_id=risk_id,
            category=verdict.category,
            speaker=chunk.speaker,
            level=verdict.level,
            trigger="keyword+llm",
            keyword=hint.keyword,
            llm_confidence=verdict.confidence,
            text=chunk.text,
        )
        await self._on_event(event)
        self._mark_emit(verdict.category)

    async def _llm_free_scan(self, chunk: TranscriptChunk) -> None:
        verdict = await analyze_risk_with_llm(
            transcript_text=chunk.text,
            speaker=chunk.speaker,
            keyword_hint=None,
        )
        if not verdict.is_risk:
            return
        if not self._should_emit(verdict.category):
            return
        risk_id = str(uuid.uuid4())
        event = self._build_event(
            risk_id=risk_id,
            category=verdict.category,
            speaker=chunk.speaker,
            level=verdict.level,
            trigger="llm",
            keyword=None,
            llm_confidence=verdict.confidence,
            text=chunk.text,
        )
        await self._on_event(event)
        self._mark_emit(verdict.category)

    def _should_emit(self, category: str) -> bool:
        last = self._last_emit.get(category, 0.0)
        return (time.monotonic() - last) >= settings.risk_dedup_window_sec

    def _mark_emit(self, category: str) -> None:
        self._last_emit[category] = time.monotonic()

    @staticmethod
    def _build_event(
        risk_id: str,
        category: str,
        speaker: str,
        level: str,
        trigger: str,
        keyword: Optional[str],
        llm_confidence: Optional[float],
        text: str,
    ) -> dict:
        return {
            "type": "risk.event",
            "id": risk_id,
            "category": category,
            "speaker": speaker,
            "level": level,
            "trigger": trigger,
            "matched_keyword": keyword,
            "llm_confidence": llm_confidence,
            "transcript_text": text,
            "ts_ms": int(time.time() * 1000),
            "raised_at": datetime.now(timezone.utc).isoformat(),
        }
