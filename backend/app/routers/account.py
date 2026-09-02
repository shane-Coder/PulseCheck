from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.security import hash_password, verify_password
from app.templating import templates

router = APIRouter(prefix="/account", tags=["account"])
COOKIE_NAME = "access_token"


@router.get("")
def account_home(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        "account.html", {"request": request, "user": user, "error": None, "success": None}
    )


@router.post("/display-name")
def update_display_name(
    request: Request,
    display_name: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user.display_name = display_name.strip() or None
    db.commit()
    return templates.TemplateResponse(
        "account.html",
        {"request": request, "user": user, "error": None, "success": "Display name updated."},
    )


@router.post("/password")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(current_password, user.hashed_password):
        return templates.TemplateResponse(
            "account.html",
            {"request": request, "user": user, "error": "Current password is incorrect.", "success": None},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if len(new_password) < 8:
        return templates.TemplateResponse(
            "account.html",
            {"request": request, "user": user, "error": "New password must be at least 8 characters.", "success": None},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if len(new_password.encode("utf-8")) > 72:
        return templates.TemplateResponse(
            "account.html",
            {"request": request, "user": user, "error": "Password must be 72 characters or fewer.", "success": None},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user.hashed_password = hash_password(new_password)
    db.commit()
    return templates.TemplateResponse(
        "account.html",
        {"request": request, "user": user, "error": None, "success": "Password updated."},
    )


@router.post("/delete")
def delete_account(
    request: Request,
    current_password: str = Form(...),
    confirm_email: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(current_password, user.hashed_password):
        return templates.TemplateResponse(
            "account.html",
            {"request": request, "user": user, "error": "Current password is incorrect.", "success": None},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if confirm_email.strip().lower() != user.email.lower():
        return templates.TemplateResponse(
            "account.html",
            {"request": request, "user": user, "error": "Typed email didn't match your account email.", "success": None},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    db.delete(user)
    db.commit()

    response = RedirectResponse(url="/register", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(COOKIE_NAME)
    return response
