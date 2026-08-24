import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MonitorStatus(str, enum.Enum):
    NEW = "new"        # created, never pinged yet
    UP = "up"          # pinged within the expected window
    DOWN = "down"       # overdue, alert has fired
    PAUSED = "paused"    # user disabled checks


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Stamped on register/login. Combined with each monitor's last_ping_at to
    # decide real inactivity — a monitor quietly doing its job for months
    # without the owner ever opening the dashboard is the *intended* use
    # case, not inactivity, so logins alone would be the wrong signal.
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 0 = no reminder sent, 1 = first reminder sent, 2 = second/final sent.
    # Reset to 0 on any login or ping, so becoming active again cancels it.
    inactivity_reminder_stage: Mapped[int] = mapped_column(Integer, default=0)

    monitors: Mapped[list["Monitor"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Monitor(Base):
    __tablename__ = "monitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ping_token: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))

    # How often the job is expected to ping, and how much slack before we call it "down".
    period_seconds: Mapped[int] = mapped_column(Integer, default=86400)   # e.g. 1 day
    grace_seconds: Mapped[int] = mapped_column(Integer, default=3600)     # e.g. 1 hour

    status: Mapped[MonitorStatus] = mapped_column(Enum(MonitorStatus), default=MonitorStatus.NEW)
    last_ping_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped["User"] = relationship(back_populates="monitors")
    pings: Mapped[list["PingEvent"]] = relationship(back_populates="monitor", cascade="all, delete-orphan")
    status_events: Mapped[list["StatusEvent"]] = relationship(
        back_populates="monitor", cascade="all, delete-orphan", order_by="StatusEvent.changed_at"
    )

    @property
    def deadline(self) -> datetime | None:
        if self.last_ping_at is None:
            return None
        from datetime import timedelta
        return self.last_ping_at + timedelta(seconds=self.period_seconds + self.grace_seconds)


class PingEvent(Base):
    __tablename__ = "ping_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("monitors.id"), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    monitor: Mapped["Monitor"] = relationship(back_populates="pings")


class StatusEvent(Base):
    """One row per status *transition* (not per ping) — this is what lets the
    monitor detail page draw an up/down timeline and compute real uptime %,
    instead of only ever knowing the current status."""

    __tablename__ = "status_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("monitors.id"), nullable=False)
    status: Mapped[MonitorStatus] = mapped_column(Enum(MonitorStatus), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    monitor: Mapped["Monitor"] = relationship(back_populates="status_events")
