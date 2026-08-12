from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_current_user_optional
from app.models import Monitor, MonitorStatus, User
from app.templating import templates

router = APIRouter(tags=["monitors"])


@router.get("/")
def home(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    # Logged out: this is the front door — show what PulseCheck is before
    # asking anyone to sign in. Logged in: show the actual dashboard.
    if user is None:
        return templates.TemplateResponse("landing.html", {"request": request, "user": None})

    monitors = (
        db.query(Monitor)
        .filter(Monitor.owner_id == user.id)
        .order_by(Monitor.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "user": user, "monitors": monitors}
    )


@router.post("/monitors")
def create_monitor(
    name: str = Form(...),
    period_seconds: int = Form(86400),
    grace_seconds: int = Form(3600),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    monitor = Monitor(
        owner_id=user.id,
        name=name,
        period_seconds=max(period_seconds, 60),
        grace_seconds=max(grace_seconds, 0),
    )
    db.add(monitor)
    db.commit()
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


@router.get("/monitors/{monitor_id}")
def monitor_detail(
    monitor_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    monitor = (
        db.query(Monitor)
        .filter(Monitor.id == monitor_id, Monitor.owner_id == user.id)
        .first()
    )
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")

    recent_pings = sorted(monitor.pings, key=lambda p: p.received_at, reverse=True)[:20]
    return templates.TemplateResponse(
        "monitor_detail.html",
        {"request": request, "user": user, "monitor": monitor, "recent_pings": recent_pings},
    )


@router.post("/monitors/{monitor_id}/pause")
def pause_monitor(
    monitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    monitor = (
        db.query(Monitor)
        .filter(Monitor.id == monitor_id, Monitor.owner_id == user.id)
        .first()
    )
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")

    monitor.status = (
        MonitorStatus.PAUSED if monitor.status != MonitorStatus.PAUSED else MonitorStatus.NEW
    )
    db.commit()
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


@router.post("/monitors/{monitor_id}/delete")
def delete_monitor(
    monitor_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    monitor = (
        db.query(Monitor)
        .filter(Monitor.id == monitor_id, Monitor.owner_id == user.id)
        .first()
    )
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")

    db.delete(monitor)
    db.commit()
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
