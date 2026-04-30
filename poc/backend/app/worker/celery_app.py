import os

from celery import Celery

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

if os.getenv("CELERY_TASK_ALWAYS_EAGER") == "True":
    celery_app.conf.task_always_eager = True
