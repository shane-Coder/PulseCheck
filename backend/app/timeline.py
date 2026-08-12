from datetime import datetime, timedelta, timezone

from app.models import Monitor, MonitorStatus

WINDOW_DAYS = 30


def build_uptime_timeline(monitor: Monitor) -> dict:
    """Turns a monitor's StatusEvent history into renderable timeline segments
    (each with a status and a width percentage of the window) plus an uptime
    percentage. Windowed to the last WINDOW_DAYS, or since the monitor was
    created if it's younger than that.

    Monitors that existed before this feature shipped have no StatusEvent
    history yet — they'll show one segment for their current status until
    real transitions start accumulating."""
    now = datetime.now(timezone.utc)
    window_start = max(monitor.created_at, now - timedelta(days=WINDOW_DAYS))
    window_end = now

    events = sorted(monitor.status_events, key=lambda e: e.changed_at)
    prior = [e for e in events if e.changed_at < window_start]
    in_window = [e for e in events if window_start <= e.changed_at <= window_end]

    start_status = prior[-1].status if prior else (in_window[0].status if in_window else monitor.status)

    boundaries = [window_start] + [e.changed_at for e in in_window] + [window_end]
    statuses = [start_status] + [e.status for e in in_window]

    total_seconds = (window_end - window_start).total_seconds()
    segments = []
    up_seconds = 0.0

    for i in range(len(boundaries) - 1):
        seg_start, seg_end = boundaries[i], boundaries[i + 1]
        duration = (seg_end - seg_start).total_seconds()
        if duration <= 0:
            continue
        seg_status = statuses[i]
        if seg_status == MonitorStatus.UP:
            up_seconds += duration
        segments.append(
            {
                "status": seg_status.value,
                "width_pct": round((duration / total_seconds) * 100, 3) if total_seconds > 0 else 0,
                "start": seg_start,
                "end": seg_end,
            }
        )

    uptime_pct = round((up_seconds / total_seconds) * 100, 1) if total_seconds > 0 else 0.0

    return {
        "segments": segments,
        "uptime_pct": uptime_pct,
        "window_start": window_start,
        "window_end": window_end,
    }
