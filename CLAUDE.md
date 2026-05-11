# CLAUDE.md — salesdee (Presale + CRM SaaS for Thai furniture SMEs)

This file is read by Claude Code at the start of every session in this repo. It is the **source of truth for how we work here**. Follow it exactly.

---

## 1. What this project is

**salesdee** ("ขายดี" — working name) is a **multi-tenant SaaS "Presale + CRM"** for Thai SMEs, starting with the **furniture industry** as the beachhead vertical (the first/anchor customer is a furniture-sales business, "วัน.ดี.ดี."). Core flow: capture leads (LINE / web form / email / phone) → CRM pipeline → furniture-aware quotation → send via LINE/email → close → (phase 2) after-sales: order/production/delivery/installation/warranty + tax invoice/receipt/AR → (phase 3) basic accounting.

- **Full spec**: [REQUIREMENTS.md](REQUIREMENTS.md) — this is the PRD. Read the relevant section before building a feature.
- **Discovery / customer interview material**: [discovery/](discovery/)
- It is **not** a full accounting system and **not** an ERP. Scope and phases are defined in REQUIREMENTS.md §3.

---

## 2. Tech stack (decided — do not change without discussion)

| Layer | Choice |
|---|---|
| Language | Python 3.12+ (Django 6 supports 3.12–3.14) |
| Package/env manager | **uv** (not pip/poetry/pipenv) |
| Web framework | **Django 6.x** (server-rendered, batteries-included) |
| Frontend | **htmx** + **Alpine.js** (small client-side interactivity only) + **Tailwind CSS** — **no SPA, no React, no separate frontend app** |
| Template fragments | Django 6 **template partials** (`{% partialdef %}` / `{% partial %}`) for htmx-swappable regions; separate partial files only when reused across templates |
| Drag-and-drop | SortableJS |
| Database | **PostgreSQL** (with Row-Level Security for tenant isolation) |
| Background jobs | **Django Tasks** (`django.tasks` — built into Django 6): `@task` + `.enqueue()`; `TASKS` setting → DatabaseBackend; worker via `manage.py db_worker`. (A Celery/RQ backend can be swapped in later without changing call sites.) |
| Caching / sessions | Redis (Django cache backend) |
| Security headers | Django 6 built-in **CSP** (`django.middleware.csp.ContentSecurityPolicyMiddleware` + `SECURE_CSP`) |
| PDF generation | **WeasyPrint** (HTML→PDF; embed Thai font e.g. Sarabun) |
| Excel import/export | openpyxl |
| LINE | LINE Messaging API SDK (`line-bot-sdk`) |
| Lint / format | **ruff** (lint + format) |
| Type check | **mypy** + `django-stubs` |
| Tests | **pytest** + `pytest-django` |
| Task runner | `make` (see Makefile) |

**Why this stack**: it is opinionated, conventional, well-trodden, single-language, single-codebase — which is exactly what keeps an AI-written codebase consistent and small. Lean into "boring." Reach for the framework's built-in way first; don't invent structure Django already gives you.

---

## 3. Project structure

```
.
├── CLAUDE.md                 # this file
├── REQUIREMENTS.md           # the PRD
├── discovery/                # customer interview notes
├── pyproject.toml            # deps (managed by uv)
├── uv.lock
├── manage.py
├── Makefile
├── .env.example
├── config/                   # the Django project package
│   ├── settings/
│   │   ├── base.py           # shared settings (incl. TASKS, SECURE_CSP, i18n th/en, tz Asia/Bangkok)
│   │   ├── dev.py            # local dev
│   │   └── prod.py           # production
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── core/                 # shared: BaseModel, TenantScopedModel, managers, middleware, current-tenant context, mixins, utils (bahttext, thai dates, money)
│   ├── tenants/              # Tenant/Workspace model
│   ├── accounts/             # User, Membership (user↔tenant + role), auth, invites
│   ├── crm/                  # Lead, Deal/Opportunity, PipelineStage, Activity, Task
│   ├── catalog/              # ProductCategory, Product, ProductVariant, ProductOption, BundleItem
│   ├── quotes/               # SalesDocument (quotation first), SalesDocLine, revisions, statuses, PDF, sending
│   ├── billing/              # (phase 2) invoices, tax invoices, receipts, credit/debit notes, payments, AR
│   ├── accounting/           # (phase 3) chart of accounts, journal, ledger, periods
│   └── integrations/         # LINE OA, email, webhooks
├── templates/                # Django templates (base.html, partials/, per-app dirs)
├── static/                   # css (Tailwind output), js (htmx, alpine, sortable), fonts (Sarabun)
└── tests/                    # cross-cutting tests; per-app tests live in apps/<app>/tests/
```

**Where things go** — when in doubt: domain logic → the matching app; shared base classes/utils → `apps/core`; templates → `templates/<app>/`. If you're about to put tenant-related code anywhere but `apps/tenants`/`apps/core`, stop and reconsider.

---

## 4. Hard invariants — NEVER violate these

1. **Tenant isolation is absolute.** Every tenant-owned model inherits `TenantScopedModel` (has `tenant` FK). Every query is automatically scoped to the current tenant via the model manager + Postgres RLS. **Never write `if tenant.id == ...` or any per-customer special case in code.** Per-customer differences are *configuration/data in that tenant's rows*, never branches in code. If you find yourself wanting a customer-specific branch → it must become a setting/feature flag/config field instead.

2. **Money is `Decimal`, never `float`.** Use `DecimalField` (e.g. `max_digits=18, decimal_places=4` for amounts, `decimal_places=6` for rates). Do all arithmetic with `Decimal`. Quantize/round explicitly with a defined rounding mode (`ROUND_HALF_UP`) at display/total boundaries.

3. **Document numbers are generated inside a DB transaction** with a row lock / `select_for_update` on the sequence row — never with `count()+1`. Numbers must be unique per (tenant, doc type, year/branch scope). Tax-document numbers (tax invoice / credit note / debit note) must be **gap-free**; a cancelled one keeps its number and is marked "ยกเลิก".

4. **Issued tax documents are immutable.** Once a tax invoice is issued you don't edit it — you issue a credit/debit note. Same for posted journal entries in closed accounting periods. Model this with status + guards, not by trusting callers.

5. **Slow work goes to a background task, not the request.** Use `django.tasks` (`@task` + `.enqueue()`). PDF generation, email/LINE sending, Excel import, report exports, follow-up reminders — all background tasks. Requests stay fast. A tenant-scoped task must activate the tenant context first (see §5).

6. **Store rates/values as-of-the-event on the document itself.** Exchange rate, VAT rate, withholding rate at the time the document was issued live on the document/line rows (immutable snapshot), not looked up live later.

7. **Don't break the migration chain.** Always `makemigrations` after model changes, review the generated migration, never hand-edit applied migrations, never squash without intent.

---

## 5. Multi-tenancy — how it actually works (read before touching models/queries)

- `apps/core/models.py` defines `TenantScopedModel(BaseModel)` with `tenant = ForeignKey("tenants.Tenant", ...)` and a custom `TenantManager` that filters by the **current tenant** from a context var (`apps/core/current_tenant.py`).
- A middleware (`apps/core/middleware.py`) resolves the current tenant and sets the context var (+ the RLS session var). Resolution order: **(1) host** — a verified `TenantDomain` (custom domain), or the built-in subdomain `<slug>.<APP_DOMAIN>`; requests to a `PLATFORM_HOSTS` host get no tenant. **(2)** the authenticated user's first active membership. **(3)** (dev) `DEV_DEFAULT_TENANT_SLUG`. If the host resolves a tenant but the logged-in user isn't a member of it → 403.
- **Custom domains**: each tenant can map its own hostname via `tenants.TenantDomain` (admin: inline under `Tenant`) in addition to `<slug>.<APP_DOMAIN>`. The Django side (model + resolution) is in place; the **infra side is a deployment concern**: DNS (tenant points a CNAME at the app), on-demand TLS for arbitrary domains (Caddy on-demand TLS / a CDN / ALB+ACM), and `ALLOWED_HOSTS` in prod (can't be a fixed list — use `["*"]` and let the middleware reject hosts that aren't a platform host or a verified `TenantDomain`, or front with a proxy that does it). `TenantDomain` is a global model (`BaseModel`) — it *resolves* the tenant, so it's looked up before any tenant context; no RLS on it.
- **Defense in depth**: (a) app-layer manager auto-scoping, (b) Postgres Row-Level Security policies as a backstop, (c) tests that assert cross-tenant access returns nothing.
- **RLS**: every table with a `tenant_id` column gets an RLS policy via `enable_tenant_rls("table_name")` from `apps/core/migrations_utils.py` — add it in a small migration that depends on the `CreateModel` migration (see `apps/crm/migrations/0002_rls.py`). Note: it's `ENABLE ROW LEVEL SECURITY` without `FORCE`, so the table **owner** bypasses it — in single-role dev/CI (app connects as owner) RLS is a no-op and the `TenantManager` is what isolates; in production run the app as a **non-owner, non-superuser** role and set `RLS_ENABLED=true`. Don't forget the policy when you add a new tenant table.
- When writing a query: use the model's default manager — it's already scoped. Only use `Model.all_tenants` in clearly-justified places (migrations, platform-admin, background jobs that explicitly set the tenant context first) and call it out in a comment. Django admin for `TenantScopedModel`s uses `apps.core.admin.TenantScopedAdmin` (reads via `all_tenants`, shows the `tenant` column) so platform admins see across tenants.
- The default (scoped) manager fails **closed**: with no tenant active it returns nothing. `TenantScopedModel.save()` raises if there's no active tenant and `tenant` isn't set.
- Background tasks: a task that operates on a tenant must **activate the tenant context first** (`with tenant_context(tenant): ...`) before touching scoped models.
- ⚠️ **ModelForm / `ModelChoiceField` footgun**: a ModelForm binds an FK field's queryset at *class-definition time* (module import) — for a FK to a `TenantScopedModel` that's `Model.objects` evaluated with **no tenant active → an empty queryset**, so the field rejects every choice. **Always re-bind such querysets in the form's `__init__`** (per request). See `apps/crm/forms.py` (`_set_queryset`) for the pattern. Same caution for `get_object_or_404`/queries in module-level code, `Prefetch` objects defined at import, etc. — anything tenant-scoped must be evaluated inside a request/task with a tenant active.
- New model checklist: does it belong to a tenant? → inherit `TenantScopedModel` (and add `enable_tenant_rls` for its table in a migration). Is it global (Tenant, User, platform config)? → inherit `BaseModel` only. Per-tenant config that's keyed by a OneToOne/FK to Tenant (e.g. `CompanyProfile`) → `BaseModel` + that relation, and still add `enable_tenant_rls` on its table. Always add the per-model leakage test (data in tenant A invisible from tenant B — see `apps/crm/tests/test_tenant_isolation.py`).

---

## 6. Config over customization — the 3-bucket rule

When implementing anything that "varies by customer", classify it:

- **Core** — every furniture SME needs it (room grouping on quotes, per-line images, revisions, Thai tax invoice, BahtText, LINE, installment payment schedules) → build into the product.
- **Configurable** — varies but predictable (pipeline stages, payment-term presets, discount-approval thresholds, custom fields, document-number formats, withholding rates, document templates) → build as a **setting** (model rows under the tenant), with a sensible default that ships with the product. The anchor customer's specific values are *their tenant's config*, not hardcoded.
- **Bespoke** — only one customer wants it, too niche → don't build it into core. Either say no, or do it as per-tenant config/integration, or roadmap it if 3+ customers ask.

If you're unsure which bucket → ask, don't guess. Default to "make it a setting."

---

## 7. Localization / Thai specifics (this is a Thai product)

- **MVP is Thai-only.** UI and documents are in **Thai** (`LANGUAGE_CODE = "th-th"`, `USE_I18N = True` but only the `th` locale active). Write user-facing strings in Thai directly; you may still wrap them in `gettext` so that adding English later is mechanical, but don't build an English UI/templates now. **English / bilingual documents are a later phase** (see REQUIREMENTS.md) — don't add a language switcher, per-document language field, or `/en/` URLs yet.
- Dates: support both **พ.ศ. (Buddhist Era)** and ค.ศ.; default to พ.ศ. on documents. Provide helpers in `apps/core/utils/thai_dates.py`. Timezone default `Asia/Bangkok`.
- Numbers: thousands separators; currency formatting helpers in `apps/core`.
- **BahtText**: amount-to-Thai-words (handle "บาทถ้วน" / "สตางค์") in `apps/core/utils/bahttext.py` — well-tested, it's on every document.
- **VAT**: standard 7% (configurable); support per-line tax types VAT7 / VAT0 / EXEMPT / NONE in one document; support exclusive and inclusive pricing.
- **Withholding tax**: on quotations it's informational only (not deducted from totals); on payment recording (phase 2) it's actual. Common rates 1/2/3/5% — configurable.
- **Tax invoice (full form, Revenue Code §86/4)**: see REQUIREMENTS.md §5.2 for the required fields — enforce all of them when issuing.
- **PDPA**: this app processes tenants' customers' personal data → tenant = controller, we = processor. Support export/delete of a data subject's data; keep access scoped; log access. Don't add tracking/data flows beyond what the spec calls for.
- PDF generation: `apps/quotes/pdf.py` renders `templates/quotes/pdf/quotation.html` via WeasyPrint (lazy import). The PDF template currently relies on a **system Thai font** — install one in the runtime image (Linux: `fonts-thai-tlwg`) **or** bundle `Sarabun-*.ttf` in `static/fonts/` and add an `@font-face { src: url('file://…') }` to the template. Don't make the PDF fetch remote fonts at render time (slow/flaky). Keep per-line images out of the PDF until `base_url`/media serving is sorted.

---

## 8. Development workflow

### Setup / common commands (via `uv` and `make`)
```bash
uv sync                          # install deps from pyproject.toml/uv.lock
cp .env.example .env             # then fill in values
make migrate                     # uv run python manage.py migrate
make run                         # uv run python manage.py runserver
make worker                      # uv run python manage.py db_worker   (django.tasks DatabaseBackend worker)
make test                        # uv run pytest
make lint                        # uv run ruff check . && uv run ruff format --check .
make fmt                         # uv run ruff check --fix . && uv run ruff format .
make typecheck                   # uv run mypy .
make check                       # lint + typecheck + test  (run this before saying a task is done)
make makemigrations              # uv run python manage.py makemigrations
```
- Add a dependency: `uv add <pkg>` (dev: `uv add --dev <pkg>`). Never `pip install`.
- Run any management command: `uv run python manage.py <cmd>`.

### Definition of done (a change isn't done until all of these hold)
1. `make check` passes (ruff lint + format, mypy, pytest).
2. New/changed behavior has tests — including, for any tenant-scoped change, a test that a different tenant can't see/touch it.
3. Migrations generated and reviewed if models changed.
4. No new `# type: ignore`, `noqa`, or `all_tenants()` without a one-line justification comment.
5. User-facing strings are translatable; money is `Decimal`; slow work is in Celery.
6. No per-customer branches; new variability is a setting with a default.

### Tests
- pytest + pytest-django. Per-app tests in `apps/<app>/tests/`. Shared fixtures (tenant, user, membership, request-with-tenant) in `conftest.py`.
- Always run a tenant-leakage test for tenant-scoped models: create data in tenant A, assert it's invisible from tenant B's context.
- Tests are the AI's feedback loop — run them after every change; don't consider a task complete with failing tests, and report failures honestly with output.

### Code style
- Match the surrounding code's style, naming, and comment density. ruff is the formatter — don't fight it.
- Type-hint function signatures and model fields' intent. Prefer clear names over comments; comment the *why*, not the *what*.
- Keep views thin; put domain logic in `services.py` / model methods, not in views or templates.
- Templates: server-render with htmx; partials in `templates/<app>/partials/`; one fragment per htmx-swappable region. Use Alpine only for local UI state and the quote-editor live math (avoid round-trips per keystroke there).
- Forms: use Django forms / ModelForms for validation; don't hand-roll form parsing.

### Git
- This may not be a git repo yet; if asked to commit, branch first if on the default branch. **Don't commit or push unless the user asks.** End commit messages with the Co-Authored-By trailer.

---

## 9. When you (Claude) work in this repo

- Before building a feature: read the relevant REQUIREMENTS.md section; check `apps/core` for existing base classes/utils before writing new ones.
- Prefer extending the conventional Django way over introducing a new pattern. If you think a new pattern/dependency is warranted, propose it first.
- Keep the codebase small: reuse `apps/core` mixins/utils; use Django admin for internal/ops CRUD instead of building custom screens (we'll manage tenants/data via admin while we have few customers).
- If a requested change would violate a §4 invariant or the §6 rule, say so and propose the compliant alternative instead of just doing it.
- Report outcomes faithfully: if tests fail, say so with output; if you skipped something, say so.
