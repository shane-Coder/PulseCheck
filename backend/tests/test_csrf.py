from app.models import Monitor
from tests.conftest import TestingSessionLocal, register


def test_protected_post_without_csrf_token_is_rejected(client):
    register(client, email="csrf1@example.com")
    resp = client.post(
        "/monitors",
        data={"name": "no-token", "period_seconds": 3600, "grace_seconds": 600, "csrf_token": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 403


def test_protected_post_with_wrong_csrf_token_is_rejected(client):
    register(client, email="csrf2@example.com")
    resp = client.post(
        "/monitors",
        data={"name": "wrong-token", "period_seconds": 3600, "grace_seconds": 600, "csrf_token": "not-the-real-token"},
        follow_redirects=False,
    )
    assert resp.status_code == 403

    # And critically, nothing was actually created.
    db = TestingSessionLocal()
    try:
        assert db.query(Monitor).filter(Monitor.name == "wrong-token").first() is None
    finally:
        db.close()


def test_protected_post_with_correct_csrf_token_succeeds(client):
    """The normal path — same as every other test in the suite, spelled
    out explicitly here to document what "correct" looks like, since the
    `client` fixture injects this token transparently everywhere else."""
    register(client, email="csrf3@example.com")
    token = client.cookies.get("csrf_token")
    assert token  # register() itself is CSRF-exempt but still sets the cookie

    resp = client.post(
        "/monitors",
        data={"name": "right-token", "period_seconds": 3600, "grace_seconds": 600, "csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 302


def test_exempt_paths_work_without_any_csrf_token(client):
    """register/login/forgot-password happen before a session (and so a
    csrf_token cookie) exists — they'd be impossible to ever submit if
    they required one."""
    resp = client.post(
        "/register", data={"email": "csrf4@example.com", "password": "TestPass123!", "csrf_token": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 200

    client.cookies.clear()
    resp = client.post(
        "/login", data={"email": "csrf4@example.com", "password": "TestPass123!", "csrf_token": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    resp = client.post("/forgot-password", data={"email": "csrf4@example.com", "csrf_token": ""})
    assert resp.status_code == 200


def test_ping_and_internal_endpoints_are_unaffected_by_csrf(client):
    """These never use cookie auth at all (bearer tokens instead), so the
    CSRF check should never even look at them."""
    resp = client.post("/ping/not-a-real-token")
    assert resp.status_code == 404  # reached the route, not blocked by CSRF (would be 403)

    resp = client.post("/internal/run-overdue-check", headers={"X-Internal-Token": "wrong"})
    assert resp.status_code in (401, 503)  # reached the route's own auth check, not CSRF


def test_login_sets_a_fresh_csrf_cookie(client):
    register(client, email="csrf5@example.com")
    first_token = client.cookies.get("csrf_token")

    client.cookies.clear()
    login_resp = client.post(
        "/login", data={"email": "csrf5@example.com", "password": "TestPass123!"}, follow_redirects=False
    )
    assert login_resp.status_code == 302
    assert client.cookies.get("csrf_token") is not None
    # Not asserting it differs from first_token — a fresh random value each
    # time means it usually will, but that's incidental, not the contract.
