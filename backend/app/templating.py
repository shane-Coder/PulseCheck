from fastapi.templating import Jinja2Templates

from app.config import settings

# Shared instance so every router renders against the same Jinja environment
# — needed so template globals (like is_admin_email below) are registered
# exactly once and available everywhere, instead of each router silently
# getting its own disconnected Jinja2Templates() with no globals.
templates = Jinja2Templates(directory="app/templates")


def is_admin_email(email: str) -> bool:
    return email.lower() in settings.admin_emails_set


templates.env.globals["is_admin_email"] = is_admin_email
