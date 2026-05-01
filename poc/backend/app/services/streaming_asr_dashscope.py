# poc/backend/app/services/streaming_asr_dashscope.py
"""DashScope paraformer-realtime-v2 streaming ASR — manually smoke-tested only."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import settings

from .streaming_asr import OnError, OnTranscript, TranscriptChunk

logger = logging.getLogger(__name__)


class DashScopeStreamingASRSession:
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
