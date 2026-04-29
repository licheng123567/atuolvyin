"""ASR dispatcher：根据 settings.asr_backend 选择实现。"""
from app.core.config import settings


def transcribe(audio_url: str, hint_task_type: str | None = None,
               local_file_path: str | None = None) -> dict:
    backend = settings.asr_backend.lower()
    if backend == "mock":
        from . import asr_mock as impl
        return impl.transcribe(audio_url, hint_task_type=hint_task_type)
    if backend == "dashscope":
        from . import asr_dashscope as impl
        return impl.transcribe(audio_url, local_file_path=local_file_path)
    raise RuntimeError(f"unknown ASR_BACKEND: {settings.asr_backend}")
