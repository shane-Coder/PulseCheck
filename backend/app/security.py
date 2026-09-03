from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None


def create_purpose_token(subject: str, purpose: str, expire_minutes: int) -> str:
    """Shared by password-reset and email-verify links — a JWT is enough
    for these, no new DB table needed, as long as the "purpose" field keeps
    a reset link from being replayable as a login token or vice versa.
    Known trade-off: stateless, so there's no way to invalidate a specific
    link early (e.g. after it's been used, or if a second one is requested)
    short of adding a DB-tracked jti — acceptable for now given the short
    expiry and small scale, worth revisiting if abuse ever shows up."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {"sub": subject, "exp": expire, "purpose": purpose}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_purpose_token(token: str, purpose: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != purpose:
            return None
        return payload.get("sub")
    except JWTError:
        return None
