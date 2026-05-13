# poc/backend/app/ws/call_session.py
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from app.models.call import CallRecord
from app.models.case import CollectionCase, OwnerProfile
from app.risk.risk_detector import RiskDetector
from app.services.realtime_llm import RealtimeSuggestionEngine
from app.services.streaming_asr import TranscriptChunk, get_streaming_asr_backend

logger = logging.getLogger(__name__)


class CallSession:
    """Per-call audio-pipeline aggregator.

    Owns one ASR session + one suggestion engine + one risk detector.
    Created on first agent connection; torn down when room becomes empty
    or `call.ended` received.
    """

    def __init__(
        self,
        call_id: int,
        on_transcript_broadcast: Callable[[dict], Awaitable[None]],
        on_suggestion_broadcast: Callable[[dict], Awaitable[None]],
        on_tag_ready: Callable[[dict], Awaitable[None]],
        on_risk_broadcast: Callable[[dict], Awaitable[None]],
    ) -> None:
        self.call_id = call_id
        self._on_transcript = on_transcript_broadcast
        self._on_suggestion = on_suggestion_broadcast
        self._on_tag = on_tag_ready
        self._on_risk = on_risk_broadcast
        self._asr_session = None
        self._llm_engine: RealtimeSuggestionEngine | None = None
        self._risk_detector: RiskDetector | None = None
        self._tenant_id: int | None = None
        self._db: Session | None = None
        self._stopped: bool = False

    async def start(self, db: Session) -> None:
        self._db = db
        call = db.get(CallRecord, self.call_id)
        if not call or not call.case_id:
            logger.warning("CallSession.start: call=%s not found or missing case_id", self.call_id)
            return

        self._tenant_id = call.tenant_id
        case = db.get(CollectionCase, call.case_id)
        owner = db.get(OwnerProfile, case.owner_id) if case and case.owner_id else None
        from sqlalchemy import select

        from app.models.script import TenantSuggestionConfig
        from app.models.tenant import UserTenantMembership
        from app.services.realtime_llm import SENSITIVITY_THRESHOLD, _load_scripts

        # v1.4 S16.5 — 取 caller 的 provider_id（外勤 → 服务商话术合并）
        caller_membership = (
            db.execute(
                select(UserTenantMembership).where(
                    UserTenantMembership.user_id == call.caller_user_id,
                    UserTenantMembership.tenant_id == call.tenant_id,
                )
            )
            .scalars()
            .first()
        )
        agent_provider_id = (
            int(caller_membership.provider_id)
            if caller_membership and caller_membership.provider_id
            else None
        )
        scripts = _load_scripts(db, call.tenant_id, agent_provider_id=agent_provider_id)
        cfg = db.execute(
            select(TenantSuggestionConfig).where(TenantSuggestionConfig.tenant_id == call.tenant_id)
        ).scalar_one_or_none()
        sensitivity = SENSITIVITY_THRESHOLD.get(cfg.sensitivity if cfg else 3, 0.65)
        max_per_push = cfg.max_per_push if cfg else 3

        self._llm_engine = RealtimeSuggestionEngine(
            case=case,
            owner=owner,
            scripts=scripts,
            sensitivity_threshold=sensitivity,
            max_per_push=max_per_push,
        )
        self._risk_detector = RiskDetector(
            call_id=self.call_id,
            tenant_id=call.tenant_id,
            on_event=self._on_risk,
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
        if self._stopped:
            return
        self._stopped = True
        if self._asr_session:
            await self._asr_session.close()
            self._asr_session = None
        if self._llm_engine:
            tag = await self._llm_engine.on_call_ended()
            if tag:
                await self._on_tag(tag)
            self._llm_engine = None
        if self._risk_detector:
            self._risk_detector.cancel()
            self._risk_detector = None

    async def _handle_transcript(self, chunk: TranscriptChunk) -> None:
        await self._on_transcript(
            {
                "type": "transcript.chunk",
                "seq": chunk.seq,
                "speaker": chunk.speaker,
                "text": chunk.text,
                "ts": chunk.ts.isoformat() if hasattr(chunk.ts, "isoformat") else chunk.ts,
                "utterance_end": getattr(chunk, "utterance_end", False),
            }
        )
        if self._llm_engine:
            suggestion = await self._llm_engine.on_transcript(chunk)
            if suggestion:
                await self._on_suggestion(suggestion.to_message())
        if self._risk_detector and self._db:
            await self._risk_detector.on_utterance(chunk, db=self._db)

    async def _handle_error(self, exc: Exception) -> None:
        logger.error("ASR error call=%s: %s", self.call_id, exc)
