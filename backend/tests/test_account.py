from app.models import Monitor, User
from tests.conftest import TestingSessionLocal, login, register


def _get_user(email):
    db = TestingSessionLocal()
    try:
        return db.query(User).filter(User.email == email).first()
    finally:
        db.close()


def test_update_display_name(client):
    register(client, email="dispname@example.com")
    resp = client.post("/account/display-name", data={"display_name": "  Test User  "})
    assert resp.status_code == 200
    assert _get_user("dispname@example.com").display_name == "Test User"
    assert "Test User" in client.get("/").text


def test_change_password_wrong_current_rejected(client):
    register(client, email="pw1@example.com", password="OldPass123!")
    resp = client.post(
        "/account/password", data={"current_password": "WrongOne!", "new_password": "NewPass123!"}
    )
    assert resp.status_code == 400
    assert "incorrect" in resp.text


def test_change_password_success_round_trip(client):
    register(client, email="pw2@example.com", password="OldPass123!")
    resp = client.post(
        "/account/password", data={"current_password": "OldPass123!", "new_password": "NewPass123!"}
    )
    assert resp.status_code == 200
    assert "Password updated" in resp.text

    client.cookies.clear()
    assert login(client, email="pw2@example.com", password="OldPass123!").status_code == 401
    assert login(client, email="pw2@example.com", password="NewPass123!").status_code == 302


def test_webhooks_reject_non_https(client):
    register(client, email="wh1@example.com")
    resp = client.post(
        "/account/webhooks",
        data={"slack_webhook_url": "http://not-secure.example.com", "discord_webhook_url": "", "generic_webhook_url": ""},
    )
    assert resp.status_code == 400
    assert "https://" in resp.text
    assert _get_user("wh1@example.com").slack_webhook_url == ""


def test_webhooks_save_valid_urls(client):
    register(client, email="wh2@example.com")
    resp = client.post(
        "/account/webhooks",
        data={
            "slack_webhook_url": "https://hooks.slack.com/services/x",
            "discord_webhook_url": "",
            "generic_webhook_url": "",
        },
    )
    assert resp.status_code == 200
    assert _get_user("wh2@example.com").slack_webhook_url == "https://hooks.slack.com/services/x"


def test_webhook_test_send_requires_a_configured_url_first(client):
    register(client, email="wh3@example.com")
    resp = client.post("/account/webhooks/test/slack")
    assert resp.status_code == 400


def test_webhook_test_send_actually_calls_the_sender(client, monkeypatch):
    calls = []
    # Patched at the one place the real network call happens (inside
    # alert_utils itself) rather than per-caller — covers this endpoint
    # and the real down-alert path in tasks.py the same way.
    monkeypatch.setattr(
        "app.alert_utils._post_json", lambda url, payload, timeout=10: calls.append((url, payload))
    )
    register(client, email="wh4@example.com")
    client.post(
        "/account/webhooks",
        data={"slack_webhook_url": "https://hooks.slack.com/services/x", "discord_webhook_url": "", "generic_webhook_url": ""},
    )
    resp = client.post("/account/webhooks/test/slack")
    assert resp.status_code == 200
    assert len(calls) == 1
    assert calls[0][0] == "https://hooks.slack.com/services/x"
    assert "text" in calls[0][1]  # Slack's payload shape


def test_status_page_shows_only_opted_in_monitors_and_never_leaks_details(client):
    register(client, email="statuspage@example.com")
    client.post(
        "/monitors", data={"name": "public-mon", "period_seconds": 3600, "grace_seconds": 600}, follow_redirects=False
    )
    client.post(
        "/monitors", data={"name": "private-mon", "period_seconds": 3600, "grace_seconds": 600}, follow_redirects=False
    )

    db = TestingSessionLocal()
    try:
        public_mon = db.query(Monitor).filter(Monitor.name == "public-mon").first()
        public_mon.is_public = True
        public_mon.tags = "secret-tag"
        public_mon.notes = "sensitive internal note"
        db.commit()
        ping_token = public_mon.ping_token
        status_page_token = _get_user("statuspage@example.com").status_page_token
    finally:
        db.close()

    resp = client.get(f"/status/{status_page_token}")
    assert resp.status_code == 200
    assert "public-mon" in resp.text
    assert "private-mon" not in resp.text
    assert "secret-tag" not in resp.text
    assert "sensitive internal note" not in resp.text
    assert ping_token not in resp.text


def test_status_page_unknown_token_404s(client):
    resp = client.get("/status/does-not-exist")
    assert resp.status_code == 404


def test_status_page_with_no_public_monitors_shows_empty_state(client):
    register(client, email="emptypage@example.com")
    token = _get_user("emptypage@example.com").status_page_token
    resp = client.get(f"/status/{token}")
    assert resp.status_code == 200
    assert "Nothing shared here yet" in resp.text
