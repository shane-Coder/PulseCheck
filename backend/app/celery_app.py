from celery import Celery
from celery.schedules import schedule

from app.config import settings

celery_app = Celery(
    "pulsecheck",
    broker=settings.redis_url,
    # No result backend: nothing in this app ever reads a task's return
    # value or checks its state (no .get()/.delay()-and-wait/AsyncResult
    # anywhere) — both scheduled tasks are fire-and-forget. Configuring a
    # backend anyway means Celery writes a result to Redis on every single
    # task run for no reason, which is pure wasted command volume on a
    # billed-per-command Redis plan.
    include=["app.tasks"],
)

celery_app.conf.beat_schedule = {
    "check-overdue-monitors": {
        "task": "app.tasks.check_overdue_monitors",
        "schedule": schedule(run_every=settings.overdue_check_interval_seconds),
    },
    "check-inactive-accounts": {
        "task": "app.tasks.check_inactive_accounts",
        "schedule": schedule(run_every=settings.inactivity_check_interval_seconds),
    },
}

celery_app.conf.timezone = "UTC"
