import os

from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "autoluyin",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
)

# v0.9.0 — 定时任务调度(需运行 `celery -A app.worker.celery_app beat`)
celery_app.conf.beat_schedule = {
    # 每日 02:00 — N 天未联系自动释放公海(tenant + provider 两类 settings 各扫一次)
    "auto-release-stale-cases-daily": {
        "task": "tasks.auto_release_stale_cases",
        "schedule": crontab(hour=2, minute=0),
    },
}

if os.getenv("CELERY_TASK_ALWAYS_EAGER") == "True":
    celery_app.conf.task_always_eager = True
