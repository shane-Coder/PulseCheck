# PulseCheck

A dead-man's-switch monitoring service for cron jobs, scheduled scripts, and background tasks.

Your scheduled job pings a unique URL every time it runs. If a ping doesn't show up within
the expected window, PulseCheck alerts you by email (Slack/webhooks coming later).

## Why

Cron jobs and scheduled scripts fail silently all the time — a backup script errors out, a
disk fills up, a container never restarts. PulseCheck watches for the *absence* of a signal,
not the presence of an error, which is what makes it useful for jobs you can't otherwise
instrument.

## Stack

- **API/backend:** FastAPI
- **DB:** PostgreSQL (SQLAlchemy ORM)
- **Scheduler/queue:** Celery + Redis (Celery beat runs the "who's overdue" sweep)
- **Frontend:** server-rendered Jinja2 templates (no separate JS build for v1)
- **Auth:** email + password, JWT stored in an HttpOnly cookie
- **Alerts:** SMTP email (v1); Slack/webhook planned for v2

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

If a ping doesn't arrive within `period + grace` seconds, Celery beat marks the monitor
"down" and an alert email goes out.

## Project layout

```
backend/
  app/
    main.py           FastAPI app + route registration
    config.py          Settings via env vars
    database.py         SQLAlchemy engine/session
    models.py            User, Monitor, PingEvent
    schemas.py            Pydantic request/response models
    security.py            Password hashing + JWT
    deps.py                  Auth dependency (current_user from cookie)
    celery_app.py             Celery app + beat schedule
    tasks.py                   check_overdue_monitors, send_alert_email
    email_utils.py               SMTP sending helper
    routers/
      auth.py                     register/login/logout
      monitors.py                  CRUD + dashboard views
      ping.py                       the actual ping-receiving endpoint
    templates/                      Jinja2 HTML
    static/                          CSS
```

## Roadmap

- [x] v1: single-user monitors, email alerts, dashboard
- [ ] v2: Slack/webhook alerts, uptime % history, "start/fail" ping variants
- [ ] v3: Stripe billing, plan limits (free tier vs paid), team accounts
- [ ] v4: public status pages, API for programmatic monitor management

## Deployment

Designed to deploy on a free/cheap tier first (Fly.io, Railway, Render) via the included
Dockerfiles, then move to a self-managed Kubernetes cluster later without code changes —
`docker-compose.yml` mirrors the four services (`web`, `worker`, `beat`, `db`/`redis`) that
would become K8s Deployments.

## Notes

Built and maintained by [Shivam](https://github.com/shane-Coder), with Claude Code used as a
development tool for scaffolding and debugging.
