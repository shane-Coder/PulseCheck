# These env vars have to be set before ANY `app.*` module is imported —
# app.config.Settings() reads them once at import time, and app.rate_limit
# builds its Limiter (bound to whatever REDIS_URL it saw) at import time
# too. pytest always loads conftest.py before collecting test modules, so
# this is the one place that ordering is guaranteed.
import os

os.environ["REDIS_URL"] = "memory://"  # in-process rate-limit storage — no real Redis needed to run these
os.environ["DATABASE_URL"] = "sqlite:///:memory:"  # unused for real queries (see engine patch below), just harmless
os.environ["JWT_SECRET"] = "test-secret-not-for-real-use"
os.environ["SMTP_HOST"] = ""  # empty = send_email takes its "skip" branch instead of trying a real connection
os.environ["ADMIN_EMAILS"] = ""
os.environ["BASE_URL"] = "http://testserver/"
os.environ["MAINTENANCE_MODE"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.database import Base, get_db
from app.rate_limit import limiter

# StaticPool: a plain sqlite:///:memory: engine gives every new connection
# its own empty database, which breaks the moment a request opens a second
# connection. StaticPool keeps this whole test run on the one connection
# that has the tables in it.
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


main_module.app.dependency_overrides[get_db] = _override_get_db
# main.on_startup() calls Base.metadata.create_all(bind=engine) using the
# name `engine` as it exists in app.main's own namespace at call time —
# reassigning it here (not app.database.engine, which main.py already has
# its own bound copy of) is what actually redirects that call to sqlite.
main_module.engine = test_engine

# app.tasks doesn't go through the get_db dependency at all — it opens its
# own session via a module-level `SessionLocal` it imported directly from
# app.database. Same fix as above, same reason: without this, calling
# check_overdue_monitors() in a test would silently talk to a completely
# different (real, empty) database instead of the one the test just set up.
import app.tasks as tasks_module

tasks_module.SessionLocal = TestingSessionLocal


@pytest.fixture(autouse=True)
def _fresh_schema():
    """Every test gets its own empty set of tables — no leakage between
    tests, and no dependence on running them in any particular order."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """The in-memory rate-limit storage is one global store for the whole
    pytest process, not per-test like the DB above — without this, a test
    later in the file legitimately gets 429'd by a test that ran before it
    and used up the same endpoint's quota, since every test looks like the
    same client to slowapi."""
    limiter.reset()
    yield


@pytest.fixture
def client():
    with TestClient(main_module.app) as c:
        yield c


def register(client, email="user@example.com", password="TestPass123!"):
    # follow_redirects=False everywhere in these helpers: Starlette's
    # TestClient auto-follows redirects by default (unlike a plain httpx
    # or curl call), which would silently turn every "did this redirect to
    # the right place" assertion into "did the final page load" instead.
    return client.post("/register", data={"email": email, "password": password}, follow_redirects=False)


def login(client, email="user@example.com", password="TestPass123!"):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=False)
