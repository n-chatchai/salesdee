# salesdee — Presale + CRM for Thai SMEs (furniture-first)

> "ขายดี" — a multi-tenant SaaS for Thai SMEs (codename/working name `salesdee`).

Lead capture (LINE / web form / email / phone) → CRM pipeline → furniture-aware quotation → send via LINE/email → close → (phase 2) after-sales + tax invoice/receipt/AR → (phase 3) basic accounting.

- **Product spec / PRD**: [REQUIREMENTS.md](REQUIREMENTS.md)
- **How we work (read this if you're contributing, human or AI)**: [CLAUDE.md](CLAUDE.md)
- **Customer discovery**: [discovery/](discovery/)

## Stack

Python 3.12+ · Django 6 (template partials, `django.tasks`, built-in CSP) · htmx + Alpine.js + Tailwind · PostgreSQL (RLS) · Redis (cache) · WeasyPrint · managed with **uv**.

## Quick start

Prereqs: Python 3.12+, [uv](https://docs.astral.sh/uv/), PostgreSQL, Redis.

```bash
uv sync
cp .env.example .env          # then edit
createdb quotation            # or set DATABASE_URL to your db
make migrate
make superuser
make run                      # http://localhost:8000  (admin at /admin)
# in another terminal (background tasks):
make worker
```

## Common commands

```bash
make run            # dev server
make worker         # celery worker
make test           # pytest
make check          # lint + typecheck + test  ← run before considering work done
make fmt            # auto-fix lint + format
make makemigrations # after model changes
uv add <pkg>        # add a dependency (NOT pip install)
```

See `make help` for all targets.
