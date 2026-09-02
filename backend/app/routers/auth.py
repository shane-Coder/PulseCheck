from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, utcnow
from app.rate_limit import limiter
from app.security import create_access_token, hash_password, verify_password
from app.templating import templates

router = APIRouter(tags=["auth"])

COOKIE_NAME = "access_token"


@router.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@router.post("/register")
@limiter.limit("5/hour")
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    # Normalized once, here, so every future lookup (login, admin grants,
    # password reset if that's ever added) can compare case-insensitively
    # without remembering to re-normalize each time. Without this,
    # "Foo@x.com" and "foo@x.com" register as two different accounts, and
    # someone who typed their email in a different case at login than at
    # signup gets a confusing "invalid password" instead of logging in.
    email = email.strip().lower()

    if "@" not in email or "." not in email.rsplit("@", 1)[-1] or len(email) > 255:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Enter a valid email address."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "An account with that email already exists."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if len(password) < 8:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Password must be at least 8 characters."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # bcrypt silently ignores anything past 72 bytes rather than erroring —
    # without this check, someone who sets a 100-character password would
    # have their account effectively "protected" by only its first 72
    # bytes, with no indication that's what happened.
    if len(password.encode("utf-8")) > 72:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Password must be 72 characters or fewer."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = User(email=email, hashed_password=hash_password(password), last_login_at=utcnow())
    db.add(user)
    db.commit()

    token = create_access_token(subject=user.email)
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
    return response


@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
@limiter.limit("10/minute")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user.last_login_at = utcnow()
    user.inactivity_reminder_stage = 0
    db.commit()

    token = create_access_token(subject=user.email)
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(COOKIE_NAME)
    return response
