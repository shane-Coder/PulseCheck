from datetime import datetime, timedelta, timezone

from app.models import Monitor, MonitorStatus, User
from app.tasks import check_overdue_monitors
from tests.conftest import TestingSessionLocal, register


def _backdate_monitor(monitor_name, seconds_ago):
    db = TestingSessionLocal()
    try:
        m = db.query(Monitor).filter(Monitor.name == monitor_name).first()
        m.created_at = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
        db.commit()
    finally:
        db.close()


def _set_webhooks(email, **urls):
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        for key, value in urls.items():
            setattr(user, key, value)
        db.commit()
    finally:
        db.close()


def test_down_alert_fires_email_and_all_configured_webhooks(client, monkeypatch):
    email_calls, slack_calls, discord_calls, generic_calls = [], [], [], []
    monkeypatch.setattr("app.tasks.send_email", lambda **kw: email_calls.append(kw))
    monkeypatch.setattr("app.tasks.send_slack_alert", lambda url, text: slack_calls.append((url, text)))
    monkeypatch.setattr("app.tasks.send_discord_alert", lambda url, text: discord_calls.append((url, text)))
    monkeypatch.setattr("app.tasks.send_generic_webhook", lambda url, payload: generic_calls.append((url, payload)))

    register(client, email="alerttest@example.com")
    _set_webhooks(
        "alerttest@example.com",
        slack_webhook_url="https://hooks.slack.com/services/x",
        discord_webhook_url="https://discord.com/api/webhooks/y",
        generic_webhook_url="https://example.com/hook",
    )
    client.post(
        "/monitors", data={"name": "down-test", "period_seconds": 60, "grace_seconds": 0}, follow_redirects=False
    )
    _backdate_monitor("down-test", seconds_ago=120)  # period+grace = 60s, so well past due

    changed = check_overdue_monitors()
    assert changed == 1

    assert len(email_calls) == 1
    assert email_calls[0]["to"] == "alerttest@example.com"
    assert len(slack_calls) == 1 and slack_calls[0][0] == "https://hooks.slack.com/services/x"
    assert len(discord_calls) == 1 and discord_calls[0][0] == "https://discord.com/api/webhooks/y"
    assert len(generic_calls) == 1 and generic_calls[0][1]["event"] == "monitor.down"

    db = TestingSessionLocal()
    try:
        m = db.query(Monitor).filter(Monitor.name == "down-test").first()
        assert m.status == MonitorStatus.DOWN
        assert m.alert_sent is True
    finally:
        db.close()


def test_down_alert_does_not_fire_twice_for_the_same_outage(client, monkeypatch):
    email_calls = []
    monkeypatch.setattr("app.tasks.send_email", lambda **kw: email_calls.append(kw))
    monkeypatch.setattr("app.tasks.send_slack_alert", lambda *a: None)
    monkeypatch.setattr("app.tasks.send_discord_alert", lambda *a: None)
    monkeypatch.setattr("app.tasks.send_generic_webhook", lambda *a: None)

    register(client, email="noduplicate@example.com")
    client.post(
        "/monitors",
        data={"name": "noduplicate-test", "period_seconds": 60, "grace_seconds": 0},
        follow_redirects=False,
    )
    _backdate_monitor("noduplicate-test", seconds_ago=120)

    first_sweep = check_overdue_monitors()
    second_sweep = check_overdue_monitors()

    assert first_sweep == 1
    assert second_sweep == 0  # already DOWN, nothing changes on the second sweep
    assert len(email_calls) == 1  # and critically, not re-sent


def test_unconfigured_webhooks_never_make_a_network_call(client, monkeypatch):
    post_json_calls = []
    monkeypatch.setattr("app.tasks.send_email", lambda **kw: None)
    monkeypatch.setattr("app.alert_utils._post_json", lambda *a, **kw: post_json_calls.append(a))

    register(client, email="nowebhooks@example.com")
    client.post(
        "/monitors", data={"name": "nowebhook-test", "period_seconds": 60, "grace_seconds": 0}, follow_redirects=False
    )
    _backdate_monitor("nowebhook-test", seconds_ago=120)

    check_overdue_monitors()

    # send_slack_alert/send_discord_alert/send_generic_webhook all early-
    # return on an empty URL — none of them should ever reach _post_json.
    assert post_json_calls == []


def test_late_transition_does_not_send_any_alert(client, monkeypatch):
    email_calls = []
    monkeypatch.setattr("app.tasks.send_email", lambda **kw: email_calls.append(kw))

    register(client, email="latetest@example.com")
    # period=60s, grace=3600s -> late at +60s, down at +3660s.
    # Backdating 90s puts it well past late but nowhere near down.
    client.post(
        "/monitors", data={"name": "late-test", "period_seconds": 60, "grace_seconds": 3600}, follow_redirects=False
    )
    _backdate_monitor("late-test", seconds_ago=90)

    changed = check_overdue_monitors()
    assert changed == 1

    db = TestingSessionLocal()
    try:
        m = db.query(Monitor).filter(Monitor.name == "late-test").first()
        assert m.status == MonitorStatus.LATE
    finally:
        db.close()

    assert email_calls == []
