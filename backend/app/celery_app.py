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

# Kombu's Redis broker transport defaults to a sub-second polling interval
# for the broker queue — sensible for a real-time task queue, pure waste
# here: our fastest scheduled task only needs to run once a minute, and a
# missed monitor check being picked up a few seconds late is completely
# unnoticeable. Confirmed via Redis INFO this was a real, ongoing
# contributor to command volume on a per-command-billed plan.
celery_app.conf.broker_transport_options = {"polling_interval": 5.0}
