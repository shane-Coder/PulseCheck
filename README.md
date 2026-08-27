# PulseCheck

A dead-man's-switch monitoring service for cron jobs, scheduled scripts, and background tasks.

Your scheduled job pings a unique URL every time it finishes successfully. If a ping doesn't
show up within the expected window, PulseCheck assumes something broke and emails you —
before you find out the hard way, days later.

Live: **https://pulsecheck-shivam.fly.dev**

## Why

Most monitoring (Prometheus, UptimeRobot, etc.) watches things that are already running.
Nothing watches for a cron job that never started, or a script that crashed before finishing —
that's the gap this fills. PulseCheck watches for the *absence* of a signal, not the presence
of an error.

## Features

- Ping-based monitoring: one `curl` call at the end of any job (cron, Docker, Kubernetes
  CronJob, CI step, systemd timer — anything that can make an HTTP request)
- Per-monitor expected interval + grace period, email alerts via SMTP
- Uptime timeline and uptime % per monitor, computed from real status-transition history
- Prometheus-compatible `/metrics` endpoint, scoped per account with a token, for pinning
  monitors onto an existing Grafana dashboard
- Admin panel (env-var-gated) to see and manage accounts
- Self-service account settings: change password, delete your own account
- Rate-limited login/register, inactivity reminders + auto-delete for abandoned accounts
- Public landing page + docs — no login wall on the marketing/explanation pages

## Stack

- **API/backend:** FastAPI
- **DB:** PostgreSQL (SQLAlchemy ORM)
- **Scheduler/queue:** Celery + Redis (beat runs the "who's overdue" sweep and the daily
  inactivity check — embedded in the worker process via `celery worker --beat`, since this
  runs as a single worker instance)
- **Frontend:** server-rendered Jinja2 templates (no separate JS build)
- **Auth:** email + password, JWT stored in an HttpOnly cookie
- **Alerts:** SMTP email (Slack/webhooks planned)

## Local development

```bash
cp .env.example .env
docker compose up --build
```

Then visit http://localhost:8000, register an account, and create a monitor. Each monitor
gets a ping URL like:

```
http://localhost:8000/ping/<token>
```

Point a cron job at it, e.g.:

```bash
* * * * * /path/to/your/script.sh && curl -fsS http://localhost:8000/ping/<token>
```

If a ping doesn't arrive within `period + grace` seconds, the scheduler marks the monitor
"down" and an alert email goes out. See `/docs` on a running instance for integration
examples (Docker, Kubernetes, GitHub Actions, systemd, Airflow) and how this fits next to
Prometheus/Grafana.

`.env.example` has every setting, including `ADMIN_EMAILS` (comma-separated emails that get
`/admin` access) and the inactivity-cleanup thresholds. Without real SMTP credentials, emails
are logged instead of sent — fine for local dev, but you'll want a real provider (Brevo,
SendGrid, etc.) for anything beyond that.

## Project layout

```
backend/
  app/
    main.py              FastAPI app + route registration
    config.py             Settings via env vars
    database.py            SQLAlchemy engine/session
    templating.py            Shared Jinja2 environment + template globals
    models.py                  User, Monitor, PingEvent, StatusEvent
    security.py                  Password hashing + JWT
    deps.py                        Auth dependencies (current user, admin gate)
    rate_limit.py                   Redis-backed rate limiting (slowapi)
    timeline.py                      Uptime-timeline computation from StatusEvent history
    celery_app.py                     Celery app + beat schedule
    tasks.py                            Overdue sweep, inactivity reminders/deletion
    email_utils.py                       SMTP sending helper
    routers/
      auth.py                              register/login/logout
      account.py                            change password, delete account, metrics URL
      admin.py                              account list + delete (env-gated)
      monitors.py                           dashboard, monitor CRUD + edit, uptime timeline
      ping.py                                the actual ping-receiving endpoint
      metrics.py                            per-account Prometheus scrape endpoint
      pages.py                              /docs
    templates/                              Jinja2 HTML (landing, dashboard, docs, admin, ...)
    static/                                  CSS
```

## Roadmap

- [x] v1: monitors, email alerts, dashboard
- [x] v2: uptime % history, Prometheus metrics, admin panel, account self-service
- [ ] v3: Slack/generic webhook alerts, "start"/"fail" ping variants
- [ ] v4: Stripe billing + plan limits, team accounts, public status pages, an API

## Deployment

Deployed on Fly.io (`fly.toml` in `backend/`) — one always-on worker (with beat embedded),
one auto-stop-when-idle web process, a small Postgres cluster, and Upstash Redis. Nothing
Fly-specific in the code itself; `docker-compose.yml` maps directly onto whatever
Docker-based host you'd rather use (Railway, Render, your own box).

## License

MIT — see [LICENSE](LICENSE).

## Notes

Built and maintained by [Shivam](https://github.com/shane-Coder), with Claude Code used as a
development tool for scaffolding and debugging.
