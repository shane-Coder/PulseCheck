from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.security import decode_access_token


def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if access_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    email = decode_access_token(access_token)
    if email is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.email.lower() not in settings.admin_emails_set:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def get_current_user_optional(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    if access_token is None:
        return None
    email = decode_access_token(access_token)
    if email is None:
        return None
    return db.query(User).filter(User.email == email).first()
