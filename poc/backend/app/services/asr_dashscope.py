"""阿里云 DashScope 流式语音识别适配（paraformer-realtime-v2）。

直接读取本地录音文件，用 ffmpeg 转成 PCM 后流式送入 DashScope，
无需公网 URL，无需 OSS，本地开发环境开箱即用。
"""
import subprocess
import time
import logging
from typing import Optional

import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

from app.core.config import settings

logger = logging.getLogger(__name__)
dashscope.api_key = settings.dashscope_api_key


def transcribe(audio_url: str, local_file_path: Optional[str] = None) -> dict:
    if not local_file_path:
        raise RuntimeError("DashScope ASR 需要 local_file_path（无公网 URL 支持）")
    return _stream_transcribe(local_file_path)


def _stream_transcribe(file_path: str) -> dict:
    # 用 ffmpeg 转成 16kHz mono PCM
    logger.info("converting %s to PCM for streaming ASR", file_path)
    try:
        pcm = subprocess.check_output(
            ["ffmpeg", "-i", file_path, "-ar", "16000", "-ac", "1", "-f", "s16le", "-"],
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg 转换失败: {e}")

    sentences: list[str] = []
    done = [False]
    error = [None]

    class _CB(RecognitionCallback):
        def on_open(self): pass
        def on_close(self): done[0] = True
        def on_complete(self): done[0] = True
        def on_error(self, result):
            error[0] = result
            done[0] = True
        def on_event(self, result: RecognitionResult):
            s = result.get_sentence()
            if s and RecognitionResult.is_sentence_end(s):
                text = s.get("text", "").strip()
                if text:
                    sentences.append(text)

    rec = Recognition(
        model="paraformer-realtime-v2",
        format="pcm",
        sample_rate=16000,
        callback=_CB(),
    )
    rec.start()
    chunk = 3200  # 100ms per chunk
    for i in range(0, len(pcm), chunk):
        rec.send_audio_frame(pcm[i : i + chunk])
        time.sleep(0.01)
    rec.stop()

    # 等待结果最多 10 秒
    deadline = time.time() + 10
    while not done[0] and time.time() < deadline:
        time.sleep(0.2)

    if error[0]:
        raise RuntimeError(f"DashScope Recognition 错误: {error[0]}")

    full_text = " ".join(sentences)
    logger.info("ASR done, %d sentences, text=%s", len(sentences), full_text[:80])
    return {
        "full_text": full_text,
        "segments": [],
        "model": "paraformer-realtime-v2",
        "raw": {"sentences": sentences},
    }
