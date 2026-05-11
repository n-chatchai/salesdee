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
- ✅ **RLS plumbing**: `enable_tenant_rls()` helper (`apps/core/migrations_utils.py`) + RLS migrations for the tenant tables; `TenantScopedAdmin` base; per-model tenant-isolation test pattern. (Enforcement needs the prod two-role setup + `RLS_ENABLED=true` — see CLAUDE.md §5.)
- ✅ **CompanyProfile + BankAccount** (`apps/tenants`) — company header data for documents + admin.
- ✅ **CRM core models** (`apps/crm`) — `Customer`, `Contact`, `PipelineStage`, `Deal`, `Activity`, `Task` + admin.
- ✅ **Tenant onboarding** — `post_save` signal seeds a default furniture sales pipeline for each new `Tenant` (`apps/crm/services.py` `seed_default_pipeline`, `signals.py`).
- ✅ **CRM UI (first cut)** — pipeline **Kanban board** (SortableJS drag → htmx `move_deal` endpoint, tenant-scoped; sets status/closed_at on WON/LOST), **customer list**, **deal detail**. Nav + home wired up.
- ✅ **CRM UI round 2** — in-app **create/edit deal & customer**, **Customer 360** page, deal detail **quick-log activity** + **add task** (htmx), **task list "my work"** + overdue + mark-done (htmx), CompanyProfile auto-shell on Tenant create. Forms re-bind tenant-scoped FK querysets per request (see CLAUDE.md §5 footgun note).
- ✅ **Lead capture** — `Lead` model (+ RLS); leads list / manual entry / detail; **convert lead → Customer + Contact + Deal** (`convert_lead` service); **public embeddable enquiry form** at `/crm/intake/<tenant-slug>/` (no login, tenant from URL).
- ✅ **Custom domains (Django side)** — `tenants.TenantDomain` model; host-based tenant resolution in the middleware (verified custom domain → tenant, `<slug>.<APP_DOMAIN>` subdomain → tenant, `PLATFORM_HOSTS` → no tenant; 403 if a logged-in user hits a tenant host they don't belong to). Infra (DNS/CNAME, on-demand TLS, prod `ALLOWED_HOSTS`) still to do at deploy time.
- ✅ **Rebrand → `salesdee`** (working name; product display name in templates/docs).
- ✅ **Catalog** (`apps/catalog`) — `ProductCategory`, `Product` (furniture fields), `ProductImage`, `ProductVariant`, `ProductOption`, `BundleItem` (+ RLS); admin with inlines; product list/detail/create/edit UI; **`import_catalog` management command** (xlsx → products).
- ✅ **Quotation — round 1** (`apps/quotes`) — `DocumentNumberSequence` (per tenant/doc-type/year, `select_for_update`, gap-free), `SalesDocument`(QUOTATION) + `SalesDocLine` (room/zone grouping, per-line image, free-text or catalog-linked), **totals engine** (subtotal → end-of-bill discount allocated proportionally → VAT bases per rate → VAT 7% → grand total + withholding estimate + net expected + **BahtText** + rounding; EXCLUSIVE pricing only for now), admin with line inline, quotation list/detail/create/edit UI, non-htmx add/delete line, **create-quotation-from-deal**.
- ✅ **Quotation PDF** — `apps/quotes/pdf.py` + `templates/quotes/pdf/quotation.html` rendered via WeasyPrint (A4, page numbers, company header from `CompanyProfile`, room groups, lines table, totals box, BahtText, signature blocks); "พิมพ์ / PDF" link on the detail page. *(Thai font: needs a system Thai font / bundled Sarabun — see CLAUDE.md; per-line images not in the PDF yet.)* `make check` green (78 tests).

## Phase 1 backlog (next, suggested order — see REQUIREMENTS.md §4)

1. **Sending** — share link (signed token + expiry → public read-only quote page, no login), send via email / LINE (attach the PDF), public **accept / request-changes / reject** with e-signature (name + timestamp + IP) → updates the deal/quote status; auto follow-up tasks ("X days after sent, no reply"). §4.8
2. **Quotation — round 2** — htmx line editor (add/edit/reorder lines, live totals; pick from catalog auto-fills price/desc/tax/image); document statuses + transitions; **revisions** (snapshot on send + diff); **discount-approval workflow** (using `Membership` caps); INCLUSIVE-VAT pricing; rounding-diff line; per-line images in the PDF. §4.7
3. **Reports/dashboard** — pipeline value, win/loss + lost reasons, sales targets vs actual, quotation conversion rate. §4.9
4. **Roles & permissions** — enforce role-based access + approval caps from `Membership`. §4.15
5. **Customer import** — `import_customers` command / web import (catalog import command exists).

### Smaller follow-ups (optional, can defer)
- LINE inbound (Messaging API webhook → create/link Lead) — currently only the public web form + manual entry exist.
- **Custom-domain deployment**: pick the TLS approach (Caddy on-demand TLS / CDN / ALB+ACM), set prod `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` strategy, domain-verification flow (TXT record) before flipping `TenantDomain.verified=True`, tenant self-serve "add your domain" UI.
- Make `Deal.stage` required (+ data migration for stage-less deals); pipeline column counts refresh after a drag (HX-Trigger / OOB swap); add/edit `Contact` in-app; company-settings page; lost-reason picker when dropping a card on "ปิดไม่ได้".
- Confirm the `salesdee` name (domain/trademark) and, if changing, rename the repo dir / `config` package.

## Open product questions still to resolve (REQUIREMENTS.md §10)
MVP boundary for the anchor customer (does phase 1 need tax invoice?), target furniture sub-segment, LINE integration depth, hosting region, pricing, product name, IP/ownership arrangement with วันดีดี. Use [discovery/wandeedee-interview-short.md](discovery/wandeedee-interview-short.md).
