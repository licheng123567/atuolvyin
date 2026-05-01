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
