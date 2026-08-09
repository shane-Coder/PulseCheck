from fastapi import Request
from slowapi import Limiter

from app.config import settings


def get_client_ip(request: Request) -> str:
    # Behind Fly's proxy, request.client.host can reflect the proxy rather
    # than the real visitor. Fly sets Fly-Client-IP; fall back to the
    # standard X-Forwarded-For, then the raw connection as a last resort.
    fly_ip = request.headers.get("Fly-Client-IP")
    if fly_ip:
        return fly_ip
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Backed by Redis (already running for Celery) so limits hold across
# machine restarts and multiple web machines, not just in one process's
# memory.
limiter = Limiter(key_func=get_client_ip, storage_uri=settings.redis_url)
