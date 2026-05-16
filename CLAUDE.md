# CLAUDE.md — salesdee (Presale + CRM SaaS for Thai furniture SMEs)

This file is read by Claude Code at the start of every session in this repo. It is the **source of truth for how we work here**. Follow it exactly.

---

## 1. What this project is

**salesdee** ("ขายดี" — working name) is a **multi-tenant SaaS "Presale + CRM"** for Thai SMEs, starting with the **furniture industry** as the beachhead vertical (the first/anchor customer is a furniture-sales business, "วัน.ดี.ดี."). Core flow: capture leads (LINE / web form / email / phone) → CRM pipeline → furniture-aware quotation → send via LINE/email → close → (phase 2) after-sales: order/production/delivery/installation/warranty + tax invoice/receipt/AR → (phase 3) basic accounting.

- **Product spec**: [PRODUCT.md](PRODUCT.md) — PRD (Thai) with vision, personas, journeys, decisions.
- **Discovery / customer interview material**: [discovery/](discovery/)
- Phase 1 shipped; phase 2 (billing/AR), phase 3 (accounting) in backlog.

---

## 2. Tech stack (decided — do not change without discussion)

| Layer | Choice |
|---|---|
| Language | Python 3.12+ (Django 6 supports 3.12–3.14) |
| Package/env manager | **uv** (not pip/poetry/pipenv) |
| Web framework | **Django 6.x** (server-rendered, batteries-included) |
| Frontend | **htmx** + **Alpine.js** (small client-side interactivity only) + **Custom CSS Design System** (CSS Custom Properties) — **no SPA, no React, no separate frontend app** |
| Template fragments | Django 6 **template partials** (`{% partialdef %}` / `{% partial %}`) for htmx-swappable regions; separate partial files only when reused across templates |
| Drag-and-drop | SortableJS |
| Database | **PostgreSQL** (with Row-Level Security for tenant isolation) |
| Background jobs | **django-q2** (Redis-backed queue + cron scheduler). Decorator `@task` from `apps/core/tasks.py` (shim) → call `fn.enqueue(*args)`; worker = `manage.py qcluster`; recurring jobs are `django_q.Schedule` rows seeded by `manage.py setup_q_schedules`. Dev/tests set `Q_CLUSTER["sync"]=True` so `.enqueue()` runs inline. **No cron** — schedules live in the DB. |
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
│   │   ├── base.py           # shared settings (TASKS, SECURE_CSP, tz Asia/Bangkok)
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

1. **Tenant isolation is absolute.** Every tenant model inherits `TenantScopedModel`. Queries auto-scope via manager + RLS. Never code `if tenant.id == ...` or per-customer branches. Per-customer differences → settings/config fields, not code branches.

2. **Money is `Decimal`, never `float`.** Use `DecimalField` (`max_digits=18, decimal_places=4` for amounts; `decimal_places=6` for rates). Do arithmetic with `Decimal`. Quantize/round with `ROUND_HALF_UP` at display/total boundaries.

3. **Document numbers via DB transaction + row lock** (`select_for_update` on sequence), never `count()+1`. Unique per (tenant, doc type, year). Tax documents must be gap-free; cancelled ones keep their number, marked "ยกเลิก".

4. **Issued tax documents are immutable.** Once a tax invoice is issued you don't edit it — you issue a credit/debit note. Same for posted journal entries in closed accounting periods. Model this with status + guards, not by trusting callers.

5. **Slow work in background tasks.** Use `from apps.core.tasks import task` (`@task` + `.enqueue()`, shim over django-q2). PDF, email/LINE, Excel, exports, reminders → tasks. Keep requests fast. Tenant-scoped tasks activate context first (see §5). Recurring jobs via `django_q.Schedule` rows in `apps/core/management/commands/setup_q_schedules.py` (no cron).

6. **Store rates/values as immutable snapshots.** Exchange rate, VAT, withholding on the document/lines at issue time, not looked up later.

7. **Don't break the migration chain.** Always `makemigrations` after model changes, review it, never hand-edit applied migrations or squash without intent.

---

## 5. Multi-tenancy — how it actually works (read before touching models/queries)

**Structure**: `TenantScopedModel(BaseModel)` has `tenant = ForeignKey("tenants.Tenant", ...)` and a custom `TenantManager` that filters by the current tenant from a context var (`apps/core/current_tenant.py`).

**Tenant resolution** (middleware, `apps/core/middleware.py`, order of preference):
1. Host: verified `TenantDomain` custom domain, or built-in `<slug>.<APP_DOMAIN>` subdomain. Requests to `PLATFORM_HOSTS` get no tenant.
2. Authenticated user's first active membership.
3. (Dev) `DEV_DEFAULT_TENANT_SLUG`. If host resolves a tenant but user isn't a member → 403.

**Custom domains**: each tenant maps a hostname via `tenants.TenantDomain` (admin: inline). Django side is ready; infra side (DNS, on-demand TLS, `ALLOWED_HOSTS`) is a deployment concern. `TenantDomain` is global (`BaseModel`) — it resolves the tenant before any tenant context, so no RLS on it.

**Defense in depth**: (a) app-layer manager auto-scoping, (b) Postgres Row-Level Security policies as backstop, (c) tests that assert cross-tenant access fails.

**RLS**: every table with `tenant_id` gets an RLS policy via `enable_tenant_rls("table_name")` (in `apps/core/migrations_utils.py`). Add it in a small migration depending on `CreateModel` (see `apps/crm/migrations/0002_rls.py`). In dev/CI the table owner bypasses RLS; in prod run the app as a non-owner role and set `RLS_ENABLED=true`. Don't forget RLS when adding a new tenant table.

**Query rules**: Use the model's default manager — it's scoped automatically. Only use `Model.all_tenants` in justified places (migrations, platform-admin, background jobs that explicitly set context first) with a comment. Django admin for `TenantScopedModel` uses `TenantScopedAdmin` (reads `all_tenants`, shows `tenant` column) so admins see across tenants.

**Manager behavior**: fails closed — with no active tenant it returns nothing. `save()` raises if there's no active tenant and `tenant` isn't set.

**Background tasks**: must activate tenant context first — `with tenant_context(tenant): ...` before touching scoped models.

**⚠️ ModelForm queryset footgun**: `ModelChoiceField` for an FK to `TenantScopedModel` binds its queryset at class-definition time (module import), evaluated with no tenant active → empty queryset → every choice is rejected. Re-bind in `__init__` per request. See `apps/crm/forms.py` (`_set_queryset`). Same for `get_object_or_404`, module-level `Prefetch` objects, etc. — anything tenant-scoped must evaluate inside a request/task.

**New model checklist**: Tenant-scoped? → `TenantScopedModel` + add `enable_tenant_rls` in a migration. Global (Tenant, User, platform config)? → `BaseModel` only. Per-tenant config via OneToOne/FK to Tenant (e.g. `CompanyProfile`)? → `BaseModel` + relation, and add `enable_tenant_rls`. Always test tenant isolation (data in tenant A invisible from tenant B — see `apps/crm/tests/test_tenant_isolation.py`).

---

## 6. Config over customization — the 3-bucket rule

When implementing "varies by customer":

- **Core**: every furniture SME needs it (room grouping, per-line images, revisions, Thai tax invoice, BahtText, LINE) → build in.
- **Configurable**: varies but predictable (pipeline stages, payment terms, discount thresholds, custom fields, doc formats, rates, templates) → build as tenant settings (model rows), with defaults. Anchor customer values are their tenant config, not hardcoded.
- **Bespoke**: only one customer wants it → say no, or do as per-tenant config/integration, or roadmap if 3+ ask.

When unsure: ask, don't guess. Default to "make it a setting."

---

## 7. Thai language and localization (MVP is Thai-only)

**Language**: UI and documents in Thai. Set `LANGUAGE_CODE = "th-th"`, `USE_I18N = True`, but only `th` locale active. Write user-facing strings in Thai directly; wrap in `gettext` for mechanical English-later. Don't add language switchers, per-document language fields, or `/en/` URLs yet (later phase).

**Dates**: support both **พ.ศ. (Buddhist Era)** and **ค.ศ.**; default to พ.ศ. on documents. Use helpers in `apps/core/utils/thai_dates.py`. Timezone: `Asia/Bangkok`.

**Numbers**: thousands separators and currency formatting helpers in `apps/core`.

**BahtText**: amount-to-Thai-words (บาทถ้วน / สตางค์) in `apps/core/utils/bahttext.py` — on every document.

**VAT**: standard 7%, configurable. Support VAT7/VAT0/EXEMPT/NONE per line in one document; support exclusive and inclusive pricing.

**Withholding tax**: informational on quotations (not deducted); actual on payments (phase 2). Rates 1/2/3/5%, configurable.

**Tax invoice**: full form per Revenue Code §86/4 (seller/buyer/address/item/qty/unit/price/vat/total required) — enforce all fields when issuing.

**PDPA**: this app processes customers' personal data. Tenant = controller, we = processor. Support export/delete; keep access scoped; log it. Don't add tracking beyond spec.

**PDF fonts**: `apps/quotes/pdf.py` renders `templates/quotes/pdf/quotation.html` via WeasyPrint. Use a system Thai font (Linux: `fonts-thai-tlwg`) or bundle `Sarabun-*.ttf` in `static/fonts/` with `@font-face { src: url('file://…') }`. Don't fetch remote fonts at render time. Skip per-line images until media serving is sorted.

---

## 8. Development workflow

### Setup / common commands (via `uv` and `make`)
```bash
uv sync                          # install deps from pyproject.toml/uv.lock
cp .env.example .env             # then fill in values
make migrate                     # uv run python manage.py migrate
make run                         # uv run python manage.py runserver
make worker                      # uv run python manage.py qcluster      (django-q2 queue + scheduler)
make test                        # uv run pytest
make lint                        # uv run ruff check . && uv run ruff format --check .
make fmt                         # uv run ruff check --fix . && uv run ruff format .
make typecheck                   # uv run mypy .
make check                       # lint + typecheck + test  (run this before saying a task is done)
make makemigrations              # uv run python manage.py makemigrations
```
- Add a dependency: `uv add <pkg>` (dev: `uv add --dev <pkg>`). Never `pip install`.
- Run any management command: `uv run python manage.py <cmd>`.

### Definition of done
1. `make check` passes (lint + format + type + test).
2. New/changed behavior has tests; tenant-scoped changes include cross-tenant leakage test.
3. Migrations generated, reviewed, and applied.
4. No new `# type: ignore`, `noqa`, or `all_tenants()` without justification.
5. User strings translatable; money `Decimal`; slow work in tasks.
6. No per-customer code branches; variability is settings with defaults.

### Tests
pytest + pytest-django. Per-app tests in `apps/<app>/tests/`. Shared fixtures in `conftest.py`. Always test tenant isolation: data in A is invisible from B. Run tests after every change; don't claim done with failures.

### Code style
- Match surrounding style/naming/comment density. ruff is the formatter — use it.
- Type-hint signatures and fields. Prefer clear names over comments; comment the *why*, not the *what*.
- Keep views thin; put logic in `services.py` / model methods.
- Templates: server-render with htmx; partials in `templates/<app>/partials/`. One fragment per htmx-swappable region. Alpine only for local UI state and quote-editor live math (avoid keystroke round-trips).
- Forms: use Django forms / ModelForms for validation.

**UI must match the design**. Priority order:
1. **`design/brand-guide.html` — supreme authority.** Tokens (palette, type, spacing, radius), `.ic` icon system, logo, primitives. When brand-guide and screen decks differ, brand-guide wins.
2. **`design/backoffice.html`** (27 frames): auth, onboarding, queue, quote, customer, catalog, settings, mobile, states.
3. **`design/tenant-site.html`** (12 frames): landing, browse, product, cart, form, post-submit, LINE webview, search, mobile.
4. **`design/website.html`**: salesdee.com.
5. **`design/prd.md`**: product decisions.

When building a screen: open the matching frame and reproduce its layout/spacing/components precisely (not "functional but rough"). Cross-check tokens/icons/logos against brand-guide and override the deck where they differ. Don't hardcode colors — use `var(--…)` from the deck. AI surfaces are sage (`var(--ai)` family / `.ai-panel`), never persimmon. PDF/email templates are standalone, not the app shell. See "Porting design/*.html → Django templates" below for the CSS extraction pipeline.

### Porting design/*.html → Django templates

The design HTML files are the **source of truth** for both markup and CSS. Treat them as a one-way pipeline:

```
design/tenant-site.html  →  static/css/tenant.css       (full <style> block, verbatim)
                         →  templates/catalog/public_*.html  (per-frame body content)

design/backoffice.html   →  static/css/backoffice.css   (full <style> block, verbatim)
                         →  templates/<app>/*.html      (per-frame body content)

design/website.html      →  static/css/web.css          (full <style> block, verbatim)
                         →  templates/web/*.html        (salesdee.com — not wired yet)
```

**Three CSS files only** — `tenant.css`, `backoffice.css`, `web.css`. Each is fully self-contained (fonts + tokens + components). No shared `tokens.css` or `app.css` — three design surfaces are independent. Each file has three sections, in order: (1) verbatim deck section (from `<style>` in the design HTML) — never hand-edit; (2) **legacy hand-written CSS** for shell/per-screen classes (`.app`, `.sb-item`, `.outside-page`, etc.) that aren't in the design deck yet — to be deleted screen-by-screen as templates get re-ported to deck class names; (3) Django runtime additions tail for Alpine/htmx/message-banner/theme-switcher rules that are Django-side implementation only.

**Rules:**
1. **CSS = verbatim copy.** Extract the entire `<style>...</style>` block as-is. Never hand-edit the deck section — if it's wrong, fix it in the design HTML first, then re-extract. Partial/manual extracts cause CSS-nesting parse errors that silently swallow hundreds of rules.
2. **One frame = one template.** Each `<section class="frame-wrapper" id="X">` body content (drop the `.frame-label` and `.frame-chrome` chrome wrappers) → one Django template. Keep class names identical.
3. **Replace static demo data with template vars.** SKUs, prices, names → `{{ }}`; lists → `{% for %}`; conditionals → `{% if %}`. Don't rename classes, don't restructure markup.
4. **Base templates load exactly one CSS file.** `templates/base.html` (backoffice shell) → `backoffice.css`. `templates/catalog/_ts_base.html` (tenant public) → `tenant.css`. `templates/auth_base.html` → `backoffice.css` (auth screens live in `design/backoffice.html`). Per-screen `{% block extra_css %}` blocks should be empty unless a screen needs a one-off inline `<style>` override.
5. **Re-extract when design changes.** Treat each CSS file's deck section as a build artifact. When the designer updates `design/*.html`, re-extract — don't merge by hand. The Django additions tail is hand-maintained.
6. **Verify after extract.** Open a page in browser, run `Array.from(document.styleSheets).map(s => ({href: s.href, rules: s.cssRules.length}))` in console — the CSS file should report hundreds of rules. If only a handful parse, the file has a CSS-nesting brace mismatch and most rules got swallowed into one parent rule.

**Frame → template map (tenant-site.html, 16 frames):**

| Frame ID | Django template |
|---|---|
| `#home` | `templates/catalog/public_home.html` |
| `#category` | `templates/catalog/public_catalog.html` |
| `#product` | `templates/catalog/public_product.html` |
| `#cart` | drawer in `templates/catalog/_ts_base.html` |
| `#checkout` / `#success` | `quote_request.html` / `quote_request_thanks.html` |
| `#quote-view` | (future) read-only quote view |
| `#search` | `templates/catalog/public_search.html` |
| `#compare` | `templates/catalog/public_compare.html` |
| `#bulk` | `templates/catalog/public_bulk.html` |
| `#showroom` | `templates/catalog/public_showroom.html` |
| `#mobile` | media queries in deck CSS |
| `#ts-toggle` / `#ts-panel` | theme switcher (⏳ not built) |

**Frame → template map (backoffice.html, 19 frames):**

| Frame ID | Django template |
|---|---|
| `#brand` | reference only (lives in brand-guide.html) |
| `#sign-in` / `#sign-up` | `templates/accounts/login.html` / `register.html` |
| `#onboarding.company` / `#onboarding.brand` | `templates/onboarding/*.html` |
| `#home.line` / `#home.web` | `templates/dashboard/home_*.html` |
| `#quotation.list` / `.create` / `.detail` | `templates/quotes/*.html` |
| `#customer.list` / `.detail` | `templates/customers/*.html` |
| `#product.list` / `.edit` / `.category` | `templates/catalog/products*.html` / `category*.html` |
| `#settings` / `.quotation` / `.website.banners` | `templates/tenants/settings_*.html` |
| `#mobile` / `#state-reference` | media queries / state classes in deck CSS |

**Verify after extract:** Open a page in browser, run `Array.from(document.styleSheets).map(s => ({href: s.href, rules: s.cssRules.length}))` in console — the deck CSS should report hundreds of rules, not dozens. If only a handful parse, the file has a CSS-nesting brace mismatch and most rules got swallowed into one parent rule.

### Git
Trunk-based: commit to `main`; keep it green (`make check` passes). No long-lived branches. Small coherent commits, not giant drops. Don't commit/push unless asked. End messages with Co-Authored-By.

---

## 9. When you work in this repo

- Check PRODUCT.md before building (vision, personas, journeys). Check `apps/core` for existing utils.
- Prefer Django conventions over new patterns. Propose pattern changes first.
- Keep codebase small: reuse `apps/core`; use Django admin for CRUD instead of custom screens.
- If a change violates §4 or §6, propose the compliant alternative instead.
- Report outcomes faithfully: test failures with output, skipped work called out.
