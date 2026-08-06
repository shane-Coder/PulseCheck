from fastapi import FastAPI
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import HTTPException
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import auth, monitors, ping

app = FastAPI(title="PulseCheck")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(monitors.router)
app.include_router(ping.router)


@app.on_event("startup")
def on_startup() -> None:
    # v1: no migrations yet, just create tables if missing. Swap for Alembic
    # once the schema needs to evolve under real user data.
    Base.metadata.create_all(bind=engine)


@app.exception_handler(HTTPException)
async def auth_redirect_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401 and "text/html" in request.headers.get("accept", ""):
        return RedirectResponse(url="/login")
    return await http_exception_handler(request, exc)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
