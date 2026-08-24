from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Monitor, MonitorStatus, PingEvent, StatusEvent

router = APIRouter(tags=["ping"])


@router.get("/ping/{ping_token}")
@router.post("/ping/{ping_token}")
def ping(ping_token: str, request: Request, db: Session = Depends(get_db)):
    """The endpoint a cron job / script hits to say 'I'm alive'. No auth — the
    token itself is the secret, same pattern as Healthchecks.io."""
    monitor = db.query(Monitor).filter(Monitor.ping_token == ping_token).first()
    if monitor is None:
        raise HTTPException(status_code=404, detail="Unknown ping token")

    now = datetime.now(timezone.utc)
    was_up = monitor.status == MonitorStatus.UP

    monitor.last_ping_at = now
    monitor.status = MonitorStatus.UP
    monitor.alert_sent = False

    # A monitor actively receiving pings proves the account is in real use,
    # even if the owner never opens the dashboard — cancel any inactivity
    # reminder in progress.
    if monitor.owner.inactivity_reminder_stage != 0:
        monitor.owner.inactivity_reminder_stage = 0

    if not was_up:
        db.add(StatusEvent(monitor_id=monitor.id, status=MonitorStatus.UP, changed_at=now))

    event = PingEvent(
        monitor_id=monitor.id,
        received_at=now,
        source_ip=request.client.host if request.client else None,
    )
    db.add(event)
    db.commit()

    return {"status": "ok", "monitor": monitor.name, "received_at": now.isoformat()}
