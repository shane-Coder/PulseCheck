from datetime import datetime, timezone

from app.celery_app import celery_app
from app.database import SessionLocal
from app.email_utils import send_email
from app.models import Monitor, MonitorStatus


@celery_app.task(name="app.tasks.check_overdue_monitors")
def check_overdue_monitors() -> int:
    """Runs on a fixed interval (see celery_app.py beat schedule). Finds monitors
    whose deadline (last_ping_at + period + grace) has passed and are not already
    marked down, flips them to DOWN, and fires an alert email. Returns the count
    flipped, mainly useful for tests/logging."""
    db = SessionLocal()
    flipped = 0
    try:
        now = datetime.now(timezone.utc)
        candidates = (
            db.query(Monitor)
            .filter(Monitor.status.in_([MonitorStatus.UP, MonitorStatus.NEW]))
            .all()
        )
        for monitor in candidates:
            if monitor.last_ping_at is None:
                # Never pinged — only alert once it's had a full period+grace to check in.
                deadline = monitor.created_at
                from datetime import timedelta
                deadline = monitor.created_at + timedelta(
                    seconds=monitor.period_seconds + monitor.grace_seconds
                )
            else:
                deadline = monitor.deadline

            if deadline is not None and now > deadline:
                monitor.status = MonitorStatus.DOWN
                flipped += 1
                if not monitor.alert_sent:
                    send_alert_email(monitor.owner.email, monitor.name)
                    monitor.alert_sent = True

        db.commit()
    finally:
        db.close()

    return flipped


def send_alert_email(to_email: str, monitor_name: str) -> None:
    send_email(
        to=to_email,
        subject=f"[PulseCheck] {monitor_name} is overdue",
        body=(
            f"Monitor \"{monitor_name}\" has not checked in within its expected window.\n\n"
            "This usually means the scheduled job it's watching didn't run, or failed "
            "before it could send its ping.\n\n"
            "Log in to PulseCheck to see details."
        ),
    )
