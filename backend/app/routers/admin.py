from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin_user
from app.models import Monitor, User
from app.templating import templates, is_admin_email

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("")
def admin_home(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    rows = (
        db.query(User, func.count(Monitor.id).label("monitor_count"))
        .outerjoin(Monitor, Monitor.owner_id == User.id)
        .group_by(User.id)
        .order_by(User.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "user": admin, "rows": rows},
    )


@router.post("/users/{target_id}/delete")
def admin_delete_user(
    target_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    target = db.query(User).filter(User.id == target_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Guard against wiping out an admin account (yourself or a co-admin) via
    # a misclick in this panel — that's what account settings' self-delete
    # is for, deliberately gated behind re-entering your own password.
    if is_admin_email(target.email):
        raise HTTPException(status_code=400, detail="Can't delete an admin account from here")

    db.delete(target)
    db.commit()
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
