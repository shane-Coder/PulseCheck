from celery import Celery
from celery.schedules import schedule

from app.config import settings

celery_app = Celery(
    "pulsecheck",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.beat_schedule = {
    "check-overdue-monitors": {
        "task": "app.tasks.check_overdue_monitors",
        "schedule": schedule(run_every=settings.overdue_check_interval_seconds),
    },
}

celery_app.conf.timezone = "UTC"
