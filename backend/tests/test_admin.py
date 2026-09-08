import uuid

from app.config import settings
from app.models import User
from tests.conftest import TestingSessionLocal, login, register


def test_non_admin_cannot_access_admin_panel(client):
    register(client, email="regular@example.com")
    resp = client.get("/admin")
    assert resp.status_code == 403


def test_admin_can_access_and_lists_accounts(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    register(client, email="admin@example.com")
    resp = client.get("/admin")
    assert resp.status_code == 200
    assert "admin@example.com" in resp.text


def test_admin_panel_paginates(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin2@example.com")
    register(client, email="admin2@example.com")

    # Inserted directly rather than through /register — going through the
    # real endpoint would hit its own 5/hour rate limit almost immediately
    # and this test isn't about that limit, it's about pagination math.
    db = TestingSessionLocal()
    try:
        for i in range(30):
            db.add(
                User(
                    email=f"padding{i}@example.com",
                    hashed_password="x",
                    metrics_token=str(uuid.uuid4()),
                    status_page_token=str(uuid.uuid4()),
                )
            )
        db.commit()
    finally:
        db.close()

    page1 = client.get("/admin?page=1")
    assert "31 accounts total" in page1.text
    assert "page 1 of 2" in page1.text

    page2 = client.get("/admin?page=2")
    assert "page 2 of 2" in page2.text

    # Way out of range clamps to the last real page instead of erroring.
    clamped = client.get("/admin?page=999")
    assert clamped.status_code == 200
    assert "page 2 of 2" in clamped.text


def test_admin_cannot_delete_another_admin(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin3@example.com,coadmin@example.com")
    register(client, email="admin3@example.com")
    client.cookies.clear()
    register(client, email="coadmin@example.com")
    client.cookies.clear()
    login(client, email="admin3@example.com")

    db = TestingSessionLocal()
    try:
        target_id = db.query(User).filter(User.email == "coadmin@example.com").first().id
    finally:
        db.close()

    resp = client.post(f"/admin/users/{target_id}/delete", follow_redirects=False)
    assert resp.status_code == 400
