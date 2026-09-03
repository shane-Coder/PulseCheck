import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MonitorStatus(str, enum.Enum):
    NEW = "new"        # created, never pinged yet
    UP = "up"          # pinged within the expected window
    LATE = "late"        # past period, still inside grace — early warning, no alert yet
    DOWN = "down"           # past period + grace, alert has fired
    PAUSED = "paused"    # user disabled checks


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # Shown in the nav instead of the raw email — no product should put your
    # bare email address in the UI chrome everywhere. Falls back to email
    # wherever this is unset (see is_admin_email usage sites and templates).
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Stamped on register/login. Combined with each monitor's last_ping_at to
    # decide real inactivity — a monitor quietly doing its job for months
    # without the owner ever opening the dashboard is the *intended* use
    # case, not inactivity, so logins alone would be the wrong signal.
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 0 = no reminder sent, 1 = first reminder sent, 2 = second/final sent.
    # Reset to 0 on any login or ping, so becoming active again cancels it.
    inactivity_reminder_stage: Mapped[int] = mapped_column(Integer, default=0)

    # Bearer secret for /metrics/{token} — same pattern as Monitor.ping_token.
    # Metrics are scoped per-user rather than a single public endpoint, since
    # a public dump would leak every user's job names across the instance.
    metrics_token: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )

    # Alert channels beyond email, all optional. One set per account rather
    # than per monitor — simplest model for now, and matches how
    # metrics_token already works (account-scoped, not monitor-scoped). All
    # three fire together on the same DOWN transition the alert email does.
    slack_webhook_url: Mapped[str] = mapped_column(String(500), default="")
    discord_webhook_url: Mapped[str] = mapped_column(String(500), default="")
    generic_webhook_url: Mapped[str] = mapped_column(String(500), default="")

    monitors: Mapped[list["Monitor"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Monitor(Base):
    __tablename__ = "monitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # index=True: Postgres does NOT automatically index foreign key columns
    # (unlike the primary key they reference) — without this, the
    # dashboard's "monitors WHERE owner_id = ?" query is a sequential scan
    # over every monitor in the table, for every user, on every page load.
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ping_token: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))

    # How often the job is expected to ping, and how much slack before we call it "down".
    period_seconds: Mapped[int] = mapped_column(Integer, default=86400)   # e.g. 1 day
    grace_seconds: Mapped[int] = mapped_column(Integer, default=3600)     # e.g. 1 hour

    status: Mapped[MonitorStatus] = mapped_column(Enum(MonitorStatus), default=MonitorStatus.NEW)
    last_ping_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    # Comma-separated — good enough for organizing/scanning a list of
    # monitors without a join table. No filter-by-tag UI yet, just display.
    tags: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped["User"] = relationship(back_populates="monitors")
    pings: Mapped[list["PingEvent"]] = relationship(back_populates="monitor", cascade="all, delete-orphan")
    status_events: Mapped[list["StatusEvent"]] = relationship(
        back_populates="monitor", cascade="all, delete-orphan", order_by="StatusEvent.changed_at"
    )

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def late_at(self) -> datetime | None:
        """When this monitor enters the 'late' warning state — period has
        passed but it's still inside the grace window, so no alert yet."""
        if self.last_ping_at is None:
            return None
        from datetime import timedelta
        return self.last_ping_at + timedelta(seconds=self.period_seconds)

    @property
    def deadline(self) -> datetime | None:
        """When this monitor is actually 'down' — period + grace has passed,
        an alert fires."""
        if self.last_ping_at is None:
            return None
        from datetime import timedelta
        return self.last_ping_at + timedelta(seconds=self.period_seconds + self.grace_seconds)


class PingEvent(Base):
    __tablename__ = "ping_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("monitors.id"), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    monitor: Mapped["Monitor"] = relationship(back_populates="pings")


class StatusEvent(Base):
    """One row per status *transition* (not per ping) — this is what lets the
    monitor detail page draw an up/down timeline and compute real uptime %,
    instead of only ever knowing the current status."""

    __tablename__ = "status_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("monitors.id"), nullable=False, index=True)
    status: Mapped[MonitorStatus] = mapped_column(Enum(MonitorStatus), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    monitor: Mapped["Monitor"] = relationship(back_populates="status_events")
