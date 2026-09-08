from app.models import Monitor, MonitorStatus
from tests.conftest import TestingSessionLocal, register


def _get_monitor(name):
    db = TestingSessionLocal()
    try:
        return db.query(Monitor).filter(Monitor.name == name).first()
    finally:
        db.close()


def create_monitor(client, name="test-monitor", period_seconds=3600, grace_seconds=600):
    resp = client.post(
        "/monitors",
        data={"name": name, "period_seconds": period_seconds, "grace_seconds": grace_seconds},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    return _get_monitor(name)


def test_create_monitor_appears_on_dashboard(client):
    register(client)
    m = create_monitor(client, name="hourly-sync")
    assert m is not None
    assert m.status == MonitorStatus.NEW
    home = client.get("/")
    assert "hourly-sync" in home.text


def test_create_monitor_clamps_out_of_range_period_and_grace(client):
    register(client)
    m = create_monitor(client, name="clamp-test", period_seconds=999999999999, grace_seconds=-5)
    assert m.period_seconds == 60 * 60 * 24 * 365
    assert m.grace_seconds == 0


def test_create_monitor_blank_name_gets_generated_placeholder(client):
    register(client)
    resp = client.post(
        "/monitors",
        data={"name": "   ", "period_seconds": 3600, "grace_seconds": 600},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db = TestingSessionLocal()
    try:
        monitors = db.query(Monitor).all()
    finally:
        db.close()
    assert len(monitors) == 1
    assert monitors[0].name.startswith("monitor-")


def test_ping_flips_status_to_up_and_records_last_ping(client):
    register(client)
    m = create_monitor(client, name="ping-test")
    assert m.last_ping_at is None

    resp = client.get(f"/ping/{m.ping_token}")
    assert resp.status_code == 200

    updated = _get_monitor("ping-test")
    assert updated.status == MonitorStatus.UP
    assert updated.last_ping_at is not None


def test_ping_unknown_token_404s(client):
    resp = client.get("/ping/not-a-real-token")
    assert resp.status_code == 404


def test_pause_then_resume_toggles_status(client):
    register(client)
    m = create_monitor(client, name="pause-test")

    client.post(f"/monitors/{m.id}/pause", follow_redirects=False)
    assert _get_monitor("pause-test").status == MonitorStatus.PAUSED

    client.post(f"/monitors/{m.id}/pause", follow_redirects=False)
    assert _get_monitor("pause-test").status == MonitorStatus.NEW


def test_edit_monitor_updates_all_fields(client):
    register(client)
    m = create_monitor(client, name="edit-test")

    resp = client.post(
        f"/monitors/{m.id}/edit",
        data={
            "name": "edit-test",
            "period_seconds": 7200,
            "grace_seconds": 1200,
            "tags": "prod,db",
            "notes": "important context",
            "is_public": "1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302

    updated = _get_monitor("edit-test")
    assert updated.period_seconds == 7200
    assert updated.grace_seconds == 1200
    assert updated.tag_list == ["prod", "db"]
    assert updated.notes == "important context"
    assert updated.is_public is True


def test_edit_monitor_unchecked_checkbox_clears_is_public(client):
    """An unchecked HTML checkbox sends no field at all, not "false" — this
    confirms the bool Form(False) default actually handles that correctly."""
    register(client)
    m = create_monitor(client, name="toggle-test")
    client.post(
        f"/monitors/{m.id}/edit",
        data={"name": "toggle-test", "period_seconds": 3600, "grace_seconds": 600, "is_public": "1"},
        follow_redirects=False,
    )
    assert _get_monitor("toggle-test").is_public is True

    client.post(
        f"/monitors/{m.id}/edit",
        data={"name": "toggle-test", "period_seconds": 3600, "grace_seconds": 600},
        follow_redirects=False,
    )
    assert _get_monitor("toggle-test").is_public is False


def test_delete_monitor_removes_it(client):
    register(client)
    m = create_monitor(client, name="delete-test")
    resp = client.post(f"/monitors/{m.id}/delete", follow_redirects=False)
    assert resp.status_code == 302
    assert _get_monitor("delete-test") is None


def test_user_cannot_view_or_modify_another_users_monitor(client):
    register(client, email="ownera@example.com")
    m = create_monitor(client, name="private-monitor")

    client.cookies.clear()
    register(client, email="ownerb@example.com")

    assert client.get(f"/monitors/{m.id}").status_code == 404
    assert client.get(f"/monitors/{m.id}/edit").status_code == 404
    assert client.post(f"/monitors/{m.id}/pause", follow_redirects=False).status_code == 404
    assert client.post(f"/monitors/{m.id}/delete", follow_redirects=False).status_code == 404

    # None of those attempts should have touched it.
    assert _get_monitor("private-monitor") is not None
    assert _get_monitor("private-monitor").status == MonitorStatus.NEW
