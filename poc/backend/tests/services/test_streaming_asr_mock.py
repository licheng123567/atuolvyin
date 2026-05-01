import asyncio

import pytest


@pytest.mark.asyncio
async def test_mock_streaming_asr_emits_chunks_every_1s():
    from app.services.streaming_asr import get_streaming_asr_backend

    received: list[dict] = []

    async def on_transcript(chunk):
        received.append(chunk.model_dump())

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
