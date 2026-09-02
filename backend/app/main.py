from fastapi import FastAPI
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import HTTPException
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import Base, engine
from app.maintenance import MAINTENANCE_HTML
from app.rate_limit import limiter
from app.routers import account, admin, auth, internal, metrics, monitors, pages, ping

# docs_url/redoc_url disabled: FastAPI's built-in interactive API docs default
# to "/docs" too, which silently wins the route over our own docs page since
# it's registered before app.include_router() runs. We don't expose a public
# API surface here, so there's nothing worth keeping Swagger UI around for.
app = FastAPI(title="PulseCheck", docs_url=None, redoc_url=None)

app.state.limiter = limiter

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(account.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(internal.router)
app.include_router(metrics.router)
app.include_router(monitors.router)
app.include_router(pages.router)
app.include_router(ping.router)


@app.middleware("http")
async def maintenance_mode_middleware(request: Request, call_next):
    # /healthz stays live either way — Fly's health check hitting this
    # shouldn't depend on maintenance mode, and it never touches the DB.
    if settings.maintenance_mode and request.url.path != "/healthz":
        return HTMLResponse(MAINTENANCE_HTML, status_code=503)
    return await call_next(request)


@app.on_event("startup")
def on_startup() -> None:
    if settings.maintenance_mode:
        # Nothing downstream runs in maintenance mode (the middleware above
        # returns before any route or DB session is reached), so there's no
        # reason to require Postgres be reachable just to boot.
        return
    # v1: no migrations yet, just create tables if missing. Swap for Alembic
    # once the schema needs to evolve under real user data.
    Base.metadata.create_all(bind=engine)


@app.exception_handler(HTTPException)
async def auth_redirect_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401 and "text/html" in request.headers.get("accept", ""):
        return RedirectResponse(url="/login")
    return await http_exception_handler(request, exc)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return PlainTextResponse(
        "Too many attempts — please wait a bit and try again.",
        status_code=429,
    )


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
