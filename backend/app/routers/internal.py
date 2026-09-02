import hmac

from fastapi import APIRouter, Header, HTTPException

from app import tasks
from app.config import settings

# Hit by an external scheduler (GitHub Actions cron), not by anything in the
# UI. This is what replaced the always-on Celery worker: instead of a
# process sitting up 24/7 polling Redis for work, the check logic runs only
# when this endpoint is called — a few milliseconds every few minutes
# instead of a full-time machine.
router = APIRouter(prefix="/internal", tags=["internal"])


def _verify_token(x_internal_token: str | None) -> None:
    if not settings.internal_cron_token:
        # Refuse to run wide open — an empty configured token means the env
        # var was never set, not "auth is off".
        raise HTTPException(status_code=503, detail="Internal checks are not configured")
    if not x_internal_token or not hmac.compare_digest(x_internal_token, settings.internal_cron_token):
        raise HTTPException(status_code=401, detail="Invalid or missing token")


@router.post("/run-overdue-check")
def run_overdue_check(x_internal_token: str | None = Header(default=None)):
    """Meant to be called every 1-5 minutes. Cheap and idempotent — calling
    it early or twice in a row changes nothing beyond what's already due."""
    _verify_token(x_internal_token)
    changed = tasks.check_overdue_monitors()
    return {"monitors_changed": changed}


@router.post("/run-inactivity-check")
def run_inactivity_check(x_internal_token: str | None = Header(default=None)):
    """Meant to be called once a day. Also idempotent — each user's reminder
    stage lives in the DB, so an extra call the same day is a no-op for
    anyone already handled."""
    _verify_token(x_internal_token)
    return tasks.check_inactive_accounts()
