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
