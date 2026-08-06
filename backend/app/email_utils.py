import smtplib
from email.message import EmailMessage

from app.config import settings


def send_email(to: str, subject: str, body: str) -> None:
    """Best-effort SMTP send. Logs instead of raising if SMTP isn't configured,
    so local dev without a real mail server doesn't crash the app."""
    if not settings.smtp_host:
        print(f"[email skipped] to={to} subject={subject!r}")
        return

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    except Exception as exc:  # noqa: BLE001 - alerting must never crash the beat worker
        print(f"[email error] to={to} subject={subject!r} error={exc}")
