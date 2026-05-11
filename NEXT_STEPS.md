# Next steps

Scaffold is in place and verified — `make check` is green (ruff + mypy + pytest, 31 tests pass) on Django 6.0.5 / Python 3.14. Migrations for `tenants` and `accounts` are generated. A local `.env` (gitignored) was created pointing at a local Postgres `quotation` db; adjust as needed.

## 0. Run it
```bash
uv sync
# .env already present for local dev; edit if your Postgres differs
make migrate
make superuser
make run                        # http://localhost:8000  -> redirects to /accounts/login/
```
Then in Django admin (`/admin`): create a **Workspace (Tenant)** and a **Membership** linking your superuser to it, log into the app, confirm the home page shows the tenant name.

> Notes on brand-new Django 6.0 surface used here: built-in CSP (middleware + `SECURE_CSP` + `csp` context processor) works as scaffolded. The `django.tasks` background-task config is intentionally left unset (uses Django's default) — wire up the DB backend + `db_worker` when you need durable async; confirm exact module paths against the 6.0 docs at that point.

## What's already built
- Project plumbing: Django 6 settings split (`config/settings/{base,dev,prod}.py`), `uv` deps, `Makefile`, ruff/mypy/pytest config, `.env.example`, `.gitignore`, `CLAUDE.md` (read it).
- **Multi-tenancy foundation** (`apps/core`): `BaseModel`, `TenantScopedModel` + auto-scoping `TenantManager`, `current_tenant` context (`activate_tenant` / `tenant_context`), `CurrentTenantMiddleware`, RLS session-var hook (gated by `RLS_ENABLED`).
- `apps/tenants`: `Tenant` (workspace) model + admin.
- `apps/accounts`: email-login custom `User`, `Membership` (user↔tenant + role + approval caps), auth URLs, admin.
- Thai utils (`apps/core/utils`): `baht_text` (with tests), Buddhist-era date helpers, Decimal/money helpers.
- App skeletons with model-plan docstrings: `crm`, `catalog`, `quotes`, `billing` (phase 2), `accounting` (phase 3), `integrations`.
- Templates: `base.html` (Tailwind/htmx/Alpine via CDN, Sarabun font), `core/home.html`, `accounts/login.html`.
- Tests: `baht_text`, current-tenant machinery, smoke tests (`check` passes, login renders, home redirects/renders).

## Done so far (beyond the base scaffold)
- ✅ **RLS plumbing**: `enable_tenant_rls()` helper (`apps/core/migrations_utils.py`) + RLS migrations for the tenant tables; `TenantScopedAdmin` base; per-model tenant-isolation test pattern (`apps/crm/tests/test_tenant_isolation.py`). (Enforcement needs the prod two-role setup + `RLS_ENABLED=true` — see CLAUDE.md §5.)
- ✅ **CompanyProfile + BankAccount** (`apps/tenants`) — company header data for documents + admin.
- ✅ **CRM core models** (`apps/crm`) — `Customer`, `Contact`, `PipelineStage`, `Deal`, `Activity`, `Task` + admin (with inlines). Migrations applied, `make check` green (35 tests).

## Phase 1 backlog (next, suggested order — see REQUIREMENTS.md §4)

1. **Tenant onboarding** — when a `Tenant` is created, seed a default `PipelineStage` set + a `CompanyProfile` shell (signal or a `create_tenant` service); then make `Deal.stage` required again.
2. **CRM UI** (`apps/crm`) — pipeline **Kanban board** (htmx + SortableJS drag → POST stage change), deal detail with activity timeline + quick-log, customer list / Customer 360, task list "my work" + reminders. §4.3–4.5
3. **Lead capture** (`apps/crm` + `apps/integrations`) — embeddable web form, manual lead entry, LINE inbound (basic), assignment. §4.2
4. **Catalog** (`apps/catalog`) — `ProductCategory`, `Product` (+ images, W×D×H/material/color fields), `ProductVariant`, `ProductOption`, `BundleItem`; Excel import. §4.6
5. **Quotation** (`apps/quotes`) — `SalesDocument`(docType=QUOTATION) + `SalesDocLine` (room grouping, per-line images/options), totals engine (subtotal → end discount → VAT bases → VAT → grand total + withholding estimate + BahtText + rounding), document-number sequence (transactional), revisions, discount-approval workflow, statuses. §4.7
6. **PDF + sending** — WeasyPrint HTML template with embedded Sarabun, share link, send via LINE/email, public accept/sign view, auto follow-up tasks. §4.8
7. **Reports/dashboard** — pipeline value, win/loss + lost reasons, sales targets vs actual. §4.9
8. **Roles & permissions** — enforce role-based access + approval caps from `Membership`. §4.15
9. **Seed/import command** — load the anchor customer's catalog & customers from their Excel files (collected in discovery).

## Open product questions still to resolve (REQUIREMENTS.md §10)
MVP boundary for the anchor customer (does phase 1 need tax invoice?), target furniture sub-segment, LINE integration depth, hosting region, pricing, product name, IP/ownership arrangement with วันดีดี. Use [discovery/wandeedee-interview-short.md](discovery/wandeedee-interview-short.md).
