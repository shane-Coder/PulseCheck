from app.security import create_purpose_token
from tests.conftest import login, register


def test_register_shows_check_your_email_and_logs_in(client):
    resp = register(client)
    assert resp.status_code == 200
    assert "Check your email" in resp.text
    # Logged in immediately (cookie set) even though verification is a
    # nudge, not a gate.
    assert client.cookies.get("access_token") is not None
    home = client.get("/")
    assert "Your monitors" in home.text


def test_register_normalizes_email_case(client):
    register(client, email="Mixed.Case@Example.com")
    # A different-case login for the same address must still work — this
    # is the exact bug the case-normalization fix in auth.py addresses.
    client.cookies.clear()
    resp = login(client, email="mixed.case@example.com")
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


def test_register_rejects_duplicate_email(client):
    register(client, email="dupe@example.com")
    resp = register(client, email="dupe@example.com")
    assert resp.status_code == 400
    assert "already exists" in resp.text


def test_register_rejects_invalid_email(client):
    resp = register(client, email="not-an-email")
    assert resp.status_code == 400
    assert "valid email" in resp.text


def test_register_rejects_short_password(client):
    resp = register(client, email="short@example.com", password="short")
    assert resp.status_code == 400
    assert "at least 8 characters" in resp.text


def test_register_rejects_password_over_72_bytes(client):
    resp = register(client, email="long@example.com", password="x" * 73)
    assert resp.status_code == 400
    assert "72 characters or fewer" in resp.text


def test_login_wrong_password_rejected(client):
    register(client, email="loginuser@example.com", password="CorrectPass123!")
    client.cookies.clear()
    resp = login(client, email="loginuser@example.com", password="WrongPassword!")
    assert resp.status_code == 401


def test_login_nonexistent_user_rejected(client):
    resp = login(client, email="nobody@example.com")
    assert resp.status_code == 401


def test_forgot_password_does_not_reveal_whether_email_exists(client):
    register(client, email="real@example.com")
    resp_real = client.post("/forgot-password", data={"email": "real@example.com"})
    resp_fake = client.post("/forgot-password", data={"email": "totally-made-up@example.com"})
    assert resp_real.status_code == resp_fake.status_code == 200
    assert resp_real.text == resp_fake.text


def test_reset_password_full_round_trip(client):
    register(client, email="reset@example.com", password="OldPassword123!")
    token = create_purpose_token("reset@example.com", "reset", 30)

    resp = client.post(
        f"/reset-password/{token}", data={"new_password": "NewPassword123!"}, follow_redirects=False
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login?reset=success"

    client.cookies.clear()
    assert login(client, email="reset@example.com", password="OldPassword123!").status_code == 401
    assert login(client, email="reset@example.com", password="NewPassword123!").status_code == 302


def test_verify_token_cannot_be_used_as_reset_token(client):
    register(client, email="crosspurpose@example.com")
    verify_token = create_purpose_token("crosspurpose@example.com", "verify", 30)
    resp = client.get(f"/reset-password/{verify_token}")
    assert "Link expired" in resp.text


def test_reset_token_cannot_be_used_as_verify_token(client):
    register(client, email="crosspurpose2@example.com")
    reset_token = create_purpose_token("crosspurpose2@example.com", "reset", 30)
    resp = client.get(f"/verify-email/{reset_token}")
    assert "Link expired" in resp.text


def test_verify_email_marks_account_verified(client):
    register(client, email="verifyme@example.com")
    token = create_purpose_token("verifyme@example.com", "verify", 60)
    resp = client.get(f"/verify-email/{token}")
    assert "Email verified" in resp.text
    # Banner should be gone now.
    home = client.get("/")
    assert "Verify your email" not in home.text
