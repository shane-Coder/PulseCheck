from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from app.config import settings

# Shared instance so every router renders against the same Jinja environment
# — needed so template globals (like is_admin_email below) are registered
# exactly once and available everywhere, instead of each router silently
# getting its own disconnected Jinja2Templates() with no globals.
templates = Jinja2Templates(directory="app/templates")


def is_admin_email(email: str) -> bool:
    return email.lower() in settings.admin_emails_set


def render_time(dt, mode: str = "datetime") -> Markup:
    """Every stored timestamp is UTC — this renders it as a <time> element
    carrying the real UTC value, with UTC text as the initial/fallback
    content. base.html's script then swaps that text for the viewer's own
    browser-local timezone on page load. Not "convert to IST" specifically
    — the same page shows correct local time to anyone, anywhere, since
    the conversion happens in each viewer's own browser, not on the server.
    mode "date" omits the time-of-day part (used for "since <date>" text)."""
    if dt is None:
        return Markup("never")
    fallback = dt.strftime("%Y-%m-%d") if mode == "date" else dt.strftime("%Y-%m-%d %H:%M UTC")
    return Markup(f'<time datetime="{escape(dt.isoformat())}" data-local-time="{mode}">{escape(fallback)}</time>')


templates.env.globals["is_admin_email"] = is_admin_email
templates.env.globals["render_time"] = render_time
