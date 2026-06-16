from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "jobfinder",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)
celery_app.conf.update(
    task_track_started=True,
    timezone="Europe/London",
    enable_utc=True,
)
