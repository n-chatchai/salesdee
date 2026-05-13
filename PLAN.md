# salesdee. — development plan

Source of truth for *what* to build: `specs/salesdee-prd.md` (PRD) + `REQUIREMENTS.md` (detailed PRD).
Source of truth for *how it looks*: `specs/salesdee-design-deck.html` (24 screens), `specs/salesdee-brand-guide.html` (design system), `specs/salesdee-pdf-and-line.html` (PDF + LINE Flex templates).
Source of truth for *how we work*: `CLAUDE.md`.

> Decision (2026-05-13): the old `templates/` dir is being **rebuilt from scratch** off the design deck + a new custom-CSS design system. Old templates were deleted in the working tree on purpose.

---

## Current state

**Backend — far along.** Models exist for: tenants/accounts (User, Membership, roles), catalog (ProductCategory, Product, Variant, Option, BundleItem, images), crm (Customer, Contact, PipelineStage, Deal, Activity, Task, Lead, SalesTarget), quotes (SalesDocument + lines + revisions + share link + document-number sequence), integrations (LineIntegration, LINE webhook + push, AI draft-quotation + draft-reply). Recent commits added roles/permissions scoping, sales reports, AI/LINE drafting + tests.

**Frontend — being rebuilt.** `templates/` was wiped; `static/css/` is new. See M0.

**Gaps vs the deck/PRD (Phase 1):**
- No `Conversation` / `Message` models — the LINE webhook only spawns a `Lead`; no unified inbox.
- No Quote-from-Chat flow UI (the AI draft functions exist, no screen wiring them).
- LINE output is plain `push_text` only — no Flex Message.
- No first-run setup wizard.
- No per-tenant public homepage (public catalog/product/quotation pages do exist).
- Settings is admin-only; no in-app settings screens.
- All app templates need rebuilding from the deck.

---

## M0 — frontend foundation  *(in progress)*

- [x] `static/css/tokens.css` — design tokens (palette, radii, shadows, fonts) from the brand guide.
- [x] `static/css/app.css` — reset, paper-grain, app shell (sidebar + topbar), primitives (btn, chip, card, kpi, ai-panel, tables, forms, messages, utilities).
- [x] `templates/partials/icons.html` — lucide-style SVG sprite (`<svg class="ico"><use href="#i-…"/></svg>`).
- [x] `templates/base.html` — app shell: sidebar nav (matches deck sections), topbar (search/notifications/CTA), `messages`, blocks (`title`, `extra_css`, `nav`, `topbar`, `topbar_actions`, `content`, `body`, `extra_js`). Loads Google Fonts + htmx 2 + Alpine 3 (CDN — vendor later).
- [x] `templates/auth_base.html` + `static/css/auth.css` — centered auth/onboarding layout per deck's auth screens.
- [x] Vendor htmx 2 / alpine 3 / sortablejs into `static/js/` (base.html now serves them locally).
- [x] Self-hosted fonts: IBM Plex Sans Thai / Mono + Fraunces in `static/fonts/` + `static/css/fonts.css`; Google CDN dropped from base/auth/public templates. PDF: bundled Sarabun TTFs + `@font-face` in `pdf/quotation.html`, `pdf.py` passes `base_url = static/` (no system/remote font needed).
- [ ] Per-feature css files as screens land: `inbox.css`, `kanban.css`, `quote-editor.css`, `public.css`, `onboarding.css`.

> Note: every view currently points at a now-deleted template → expect 500s until the screen is rebuilt in its milestone. Rebuild order follows M1→M5.

## M1 — LINE unified inbox  *(mostly done)*

- [x] `apps/integrations`: `Conversation` (TenantScopedModel — channel, external_id, display_name, customer FK, lead FK, status open/snoozed/closed, assigned_to, last_message_at/preview, unread_count) + `Message` (conversation FK, direction in/out, kind text/image/sticker/file/…, text, media_url, external_id, ai_parsed jsonb, sender_user, sent_at). Migrations `0003`/`0004` + `enable_tenant_rls` on both + leakage tests.
- [x] `apps/integrations/line.py`: `get_or_create_conversation`, `_append_message`, `record_outbound_text`; `_record_inbound_text` now appends a Message + touches the Conversation **and** still mirrors onto the lead's Activity timeline (back-compat with existing webhook tests).
- [x] Inbox screen (deck "กล่องข้อความ"): 3-pane — thread list (filters: open/mine/unassigned/all) · chat transcript + composer · right rail (AI reply suggestions, extracted-lead card). htmx-driven, partials: `_thread_list`, `_conversation`, `_ai_suggestions`. `static/css/inbox.css`. Views + urls under `integrations:inbox / conversation / conversation_reply / _assign / _status / _ai_reply`. Sidebar nav points at it.
- [x] Reply: `push_text` then `record_outbound_text(sender_user=…)`; assign-to-me / unassign; close / reopen. AI suggestions via `draft_reply_from_text` (sage surfaces, "ตรวจก่อนส่งเสมอ"). + admin registration for Conversation/Message.
- [ ] LINE profile lookup to enrich `display_name` (background task).
- [ ] Image/sticker/file inbound handling (currently text-only via `process_line_events`).
- [ ] Right rail: AI customer summary (`draft`-style), linked-deal card, "สร้างใบเสนอราคา" button → M2.

### Side work done while rebuilding (so the app is navigable)
- [x] `templates/accounts/login.html` (on `auth_base.html`).
- [x] `templates/core/home.html` — placeholder dashboard (KPI tiles + quick links); full version is M5.
- [x] `templates/base.html` nav fixed to namespaced URL names (`crm:`, `catalog:`, `quotes:`, `accounts:`, `core:`, `integrations:`).

> **Known red:** `make check` is not green — ~43 tests across crm/quotes/core fail because their screen templates were deleted in the rebuild. Each turns green when its screen is rebuilt (M3 = crm/catalog/quotes screens, M5 = dashboard). New inbox code: 21 tests, all passing.

## M2 — Quote-from-Chat + LINE Flex out  *(done)*

- [x] Quote-from-Chat: inbox right rail "สร้างใบเสนอราคาจากแชตนี้" → `integrations:conversation_make_quote` → builds transcript from the conversation's Messages → `draft_quotation_from_text` (Claude) → `create_quotation_from_ai_draft` (DRAFT doc, lines linked to catalog codes, rates snapshot per CLAUDE.md §4.6) → links `SalesDocument.source_conversation` (+ pre-fills `customer` from the conversation) → redirects to the quote editor for review (no auto-send — §10 "เซลส์ตรวจก่อนเสมอ"). Reuses the existing `apps/quotes/pdf.py`.
- [x] LINE Flex out: `push_quotation_flex` in `apps/integrations/line.py` (bubble: company/doc-no header, customer/total/valid-until rows, "ดูใบเสนอราคา" + "ดาวน์โหลด PDF" URI buttons — layout per `specs/salesdee-pdf-and-line.html`). `quotation_send_line` now sends the Flex card; recipient = contact's LINE id **or** the source conversation's `external_id`; when sent into a source conversation the send is also logged as an outbound Message on that thread.
- [x] Public-link view tracking: `SalesDocument.first_viewed_at / last_viewed_at / view_count` + `record_quote_viewed` (called from `public_quotation`) — the "ลูกค้าเปิด N ครั้ง" signal. Migration `quotes/0007`.
- [x] Tests: 5 new (make-quote-from-chat, no-messages guard, Flex-to-source-conversation, no-recipient guard, view-count); updated `test_quotation_send_line` to the Flex contract. `apps/integrations` 26 tests green.
- [ ] Move PDF render + LINE send into background tasks (`django.tasks`) per CLAUDE.md §4.5 — currently synchronous in the request.
- [ ] Dedicated Quote-from-Chat review screen per deck (currently reuses the standard quote editor — needs the editor rebuilt first, M3).
- [ ] Surface "เปิด N ครั้ง" on the deal/quote screens + feed it into AI next-step suggestions (needs those screens — M3/M5).

> Note: `apps/crm/dashboard.py:157` has a pre-existing mypy error (`object * int`) from the earlier working-tree changes — not from M0–M2; fix when the dashboard is rebuilt (M5).

## M3 — CRM / pipeline / catalog / quotes UI (rebuilt from deck)  *(done)*

- [x] crm: `pipeline.html` (SortableJS kanban → `crm:move_deal`), `leads.html`, `lead_detail.html` (AI reply + AI-quotation buttons gated on `ai_enabled`, sage), `lead_form.html`, `deal_detail.html` (htmx log-activity / add-task), `deal_form.html`, `customers.html`, `customer_detail.html` (profile + contacts + deals + activities + tasks), `customer_form.html`, `tasks.html` (my-work, htmx toggle), `reports.html` (manager-only tables/bars), `intake.html` + `intake_thanks.html` (public). Partials: `_activity_list`, `_ai_reply`, `_task_list`, `_task_row`. + `templates/partials/_form.html` (shared field renderer).
- [x] catalog: `products.html`, `product_detail.html`, `product_form.html`, `public_catalog.html` (public showroom), `public_product.html` (public).
- [x] quotes: `quotations.html`, `quotation_form.html`, `quotation_detail.html` (workflow buttons + lines region + revisions link + source-conversation hint), `_quote_lines.html` (htmx add/edit/delete, SortableJS reorder), `quotation_revisions.html`, `quotation_revision_detail.html`, `public_quotation.html` (+ accept/changes/reject form), `public_quotation_invalid.html`, `public_quotation_thanks.html`, `pdf/quotation.html` (WeasyPrint, system Thai font, no remote resources). + `static/css/public.css`.
- [x] `templates/core/home.html` rebuilt as the real dashboard (no longer a stub). `templates/base.html`: topbar now shows the workspace-name chip.
- [x] **All 174 tests pass; `manage.py check` + `ruff` clean.** (Fixed up: a few templates used `var(--line)` which isn't a token — switched to `var(--border)`.)
- [ ] Pixel-level polish vs the deck (these are clean/functional, not pixel-matched) — revisit alongside the design pass.
- [ ] Customer 360: link conversations (now that `Conversation` exists) onto the customer/deal pages; show quote "เปิด N ครั้ง".
- [ ] Catalog: categories management screen + bulk actions + AI import-from-URL/PDF (still TODO).
- [ ] Quote editor: Alpine live row math (currently server-recomputes on each line change).

> **`make check` is now effectively green** — only the pre-existing `apps/crm/dashboard.py:157` mypy error (`object * int`) remains, from the earlier working-tree state; fix it in M5 when the dashboard logic is revisited (the template was rebuilt this milestone but the view code wasn't touched).

## M4 — onboarding + public homepage + settings  *(done)*

- [x] `apps/tenants/views.py` + `apps/tenants/urls.py` (`app_name="workspace"`, mounted at `/settings/`). Views: `settings_hub`, `settings_company` (CompanyProfile ModelForm, logo upload, auto-create), `settings_line` (LineIntegration form + webhook URL, masked access token), `settings_pipeline` (list + add + inline rename/kind/probability + SortableJS reorder → `pipeline_reorder`), `settings_numbering` (DocumentNumberSequence list + edit/add with the "gap-free" warning per §4.3), `settings_members` (list memberships; invite by email → creates User w/ unusable password + Membership + `send_mail(fail_silently=True)`; role/visibility/active edit guarded — not your own, not the last owner), `settings_billing` (plan tiers Free/Starter 990/Pro 2490/Business 7990 — display only), `system_status` (DB/LINE/AI/worker/RLS checklist with green/amber chips + app version). All `@login_required`; mutating ones gated to owner/manager via `_can_admin` (sales/viewer get 403). No new models.
- [x] First-run setup wizard at `/settings/welcome/` (`workspace:onboarding`), single view `?step=1..5`, progress derived from existing data (CompanyProfile name_th / logo / any Product / >1 Membership / LineIntegration configured) — no new model. Steps reuse the settings forms + `catalog.forms.ProductForm`; step 3 shows a placeholder AI "ลากไฟล์/วางลิงก์" import UI with the plain "พิมพ์ข้อมูลเอง" path working; side checklist of all 5 steps; "ย้อนกลับ / ข้ามขั้นนี้ / ต่อไป"; last step → `core:home`. Dismissible-style "ตั้งค่า workspace ให้เสร็จ — เหลือ N ขั้น" banner on `core:home` (and the settings hub) — `onboarding_remaining`/`onboarding_complete` added to the home ctx via `apps.tenants.views.onboarding_status`. No force-redirect.
- [x] Per-tenant public homepage (deck "หน้าหลักสาธารณะ"): new `apps/catalog/views.py::public_home` + `templates/catalog/public_home.html` (standalone, `static/css/{tokens,app,public,public-home}.css`) — hero (logo/name/tagline + CTA "ดูสินค้าทั้งหมด" → `public_catalog`), "เลือกตามหมวด" (top categories w/ counts), "รุ่นแนะนำ" (recent active products), "ให้ผู้ช่วยช่วยจับคู่" teaser (text box → `public_catalog?q=` when `ai_is_configured()`, else a LINE/phone contact fallback), "4 ขั้นตอน" how-it-works, contact footer. `apps/core/views.py::home` now renders this for an anonymous visitor on a tenant host instead of delegating to `public_catalog`.
- [x] `templates/base.html` nav: settings link → `{% url 'workspace:settings_hub' %}` with `ns == 'workspace'` active state. (Categories nav link left as `#` — out of M4 scope.)
- [x] Tests: `apps/tenants/tests/test_settings.py` — every settings page renders 200 for an owner / 302 for anon; viewer gets 403 on company/line/pipeline edit but 200 on the hub; member-invite creates user (unusable password) + membership and is forbidden for a viewer; company save; onboarding step 1–5 render + step-1 POST advances; `onboarding_remaining` on home; public-home renders for anon. Updated the existing `test_root_on_tenant_host_*` to the new public-home contract. **199 tests pass; `manage.py check` + `ruff` clean; `mypy apps` clean except the pre-existing `apps/crm/dashboard.py:157`.**
- [ ] Deferred: pixel polish vs the deck; functional AI catalog-match endpoint (teaser currently just hands off to the catalog search / contact); payment-term & withholding presets / custom-fields settings screens (no models yet); "customer opens quotation" public-page polish; brand-color setting (no field — shown as cosmetic only).

## M5 — dashboard + reports + mobile / PWA  *(done)*

- [x] Dashboard (`templates/core/home.html` on `apps/crm/dashboard.py`) — KPIs, pipeline table, today's tasks, awaiting/expiring quotes, new leads, lost-reasons, recent activity, monthly-target bar, onboarding banner. (Built in M3/M4; carried.)
- [x] Reports UI (`templates/crm/reports.html` on `apps/crm/reports.py`) — by-salesperson, by-month, by-channel, lost-by-reason, totals (won count/value, quotes count); manager-only per FR-15.x. (Built in M3; carried.)
- [x] Fixed the pre-existing `apps/crm/dashboard.py:157` mypy error — `_money()` now typed `Decimal | int | None -> Decimal`. `mypy apps` fully clean.
- [x] Mobile: `static/css/mobile.css` — sidebar → off-canvas drawer (`.app.nav-open`), `.app-overlay`, hamburger `.tb-menu` in topbar (Alpine `nav` state in `base.html`), responsive `.kpi-row` / inbox 3-pane stack / table-scroll. Loaded after `app.css`.
- [x] PWA: `static/manifest.json` (theme `#C8501F`, paper bg, standalone, icons) + app icons (192/512 + maskable + apple-touch + svg favicon) + `static/sw.js` (network-first, offline-page fallback, registered only off-localhost) + manifest/theme-color/apple-touch links in `base.html`.
- [x] **`make check` green** — ruff + mypy + 199 tests all pass; `collectstatic` works.
- [ ] Self-host fonts (still M0-leftover) — also unblocks the WeasyPrint PDF's Thai font (currently relies on a system font).

---

## Status — Phase-1 MVP build complete (M0–M5)

All deck screens rebuilt; LINE inbox + Quote-from-Chat + Flex out; onboarding, settings, public homepage; mobile/PWA baseline. `make check` green. Open follow-ups are tracked as unchecked `[ ]` items under each milestone above — notably: background-tasking PDF/LINE sends (CLAUDE.md §4.5), disabling the SW in DEBUG is already done, LINE profile enrichment + non-text inbound, AI customer-summary in the inbox rail, Alpine live quote-line math, and pixel-polish vs the design deck.

### M6 — gap-fill round (done)

- [x] **Categories management** (`catalog:`): list / create / edit / delete `ProductCategory` (`catalog/categories.html`, `catalog/category_form.html`, `ProductCategoryForm` with re-bound `parent` queryset). Nav link in `base.html` now points at `catalog:categories`. Reorder via Sortable not done (nice-to-have).
- [x] **Password reset + change** (`accounts:`): wired Django's built-in views; templates under `templates/registration/` (`password_reset_*`, `password_change_*`, `password_reset_email.html`). "ลืมรหัสผ่าน?" link added on the login page.
- [x] **Self-serve signup** (`accounts:signup`): `SignupForm` (workspace name/slug/owner name/email/password) → creates `Tenant` (the existing `crm.signals` post_save provisions `CompanyProfile` + default pipeline), sets `CompanyProfile.name_th`, creates the owner `User` + `Membership(owner)`, logs in, redirects to `workspace:onboarding`. "สมัครใช้งาน" link on the login page.
- [x] **Global search** (`core:search`): customers / deals / leads / quotations / products (`icontains`, capped, record-visibility scoped). Topbar search input now posts to it.
- [x] **Notifications page** (`core:notifications`): single feed from `build_notifications(request)` in `apps/crm/dashboard.py` (overdue/today tasks, awaiting/expiring quotations, unassigned/unread conversations, new leads to me). Topbar bell links to it; a context processor (`notif_count`) drives a dot.
- [x] **Customer 360 completion**: `customer_detail` now shows linked LINE conversations + the customer's quotations with `view_count` / `last_viewed_at`.
- [x] **Deal next-step hint**: rule-based (not AI) sage card on `deal_detail` — `_deal_next_step()` picks the highest-priority of: quotation viewed ≥3×, quotation expiring ≤5d, no quotation yet, no activity ≥7d.
- [x] **AI catalog-match on the public home**: `catalog:public_catalog_match` POST endpoint — uses `draft_quotation_from_text` when AI is configured (resolves `product_code`s to products), graceful fallback otherwise; htmx form on `public_home.html`. Never 500s.
- [x] Tests added for all of the above (`apps/catalog/tests/test_categories.py`, `apps/core/tests/test_search_notifications.py`, `apps/accounts/tests/test_auth_flows.py`, `apps/crm/tests/test_deal_hint_customer360.py`). `make check` green — 215 tests pass.

---

## Definition of done (per CLAUDE.md §8) — applies every milestone

`make check` green · new behavior has tests (incl. tenant-leakage test for any new scoped model) · migrations generated + reviewed · no unjustified `# type: ignore`/`noqa`/`all_tenants()` · money is `Decimal` · slow work in a background task · no per-customer branches (new variability = a setting with a default).

---

## M7 — design-polish pass (in progress)

Visual/markup-only pass to bring screens up to `specs/salesdee-design-deck.html`. No view/model/URL/permission changes.

- [x] **Dashboard** (`core/home.html`): rebuilt to the deck's D1 layout — `.d-hero` greeting + date, KPI row, `.d-grid` 2-col, `.pipeline-flow` strip, sage `.ai-digest` block, `.task-list`, `.quote-list-mini`, monthly-target bar. New `static/css/dashboard.css`.
- [x] **Pipeline kanban** (`crm/pipeline.html`): inline `<style>` moved to `static/css/kanban.css`; columns/cards restyled to the deck's `.kb-col`/`.kb-card` (customer, value, owner avatar, age); SortableJS reorder + `crm:move_deal` POST unchanged.
- [x] **List screens** — all converted to the shared `.list-head` toolbar (title + mono count pill + "+ new" button) + `.tbl` with right-aligned mono number columns / status chips / row hover: `quotes/quotations.html`, `crm/leads.html`, `crm/customers.html`, `crm/tasks.html`, `catalog/products.html`, `catalog/categories.html`. `static/css/lists.css`.
- [x] **Quote editor** (`quotes/quotation_detail.html` + `_quote_lines.html`): new `static/css/quote-editor.css` — `.qd-head` summary (doc no, customer, dates, status chip, grand-total KPI), sage `.qd-ai-banner` when `source_conversation`, styled workflow buttons row, `.qb-section-label` (Fraunces) + `.qb-header-grid` doc-info, line-items table restyled (`.qd-lines` deck look, thumbnails, dimensions, heading/note rows), bottom-right `.qb-summary` totals box + `.qb-bahttext` Fraunces line. htmx add/edit/delete/reorder + SortableJS unchanged.
- [x] **Deal detail** (`crm/deal_detail.html`): new `static/css/deal.css` — `.dd-hero` (customer avatar · value · stage chip · owner), rule-based `.dd-ai` sage next-step card, 2-col `.dd-body` (activity timeline `.tl-event` w/ icon-per-kind + log-activity/add-task htmx forms | deal facts `.dd-info-card` + notes + tasks). `crm/_activity_list.html` rewritten to the `.tl-event` timeline (icon per `Activity.kind`).
- [x] **Customer 360** (`crm/customer_detail.html`): new `static/css/customer.css` — `.c360-top` profile header (avatar, name, type/branch chips, tax id, credit), 2-col `.c360-body`: customer info card + addresses + recent-activities timeline | side cards for contacts (`.contact-row`), deals (`.open-deal`), quotations (`.quote-mini` w/ "ลูกค้าเปิด N ครั้ง · ล่าสุด …"), LINE conversations, pending tasks. Timeline `.tl-*` rules also live here (shared with deal/lead).
- [x] **Reports** (`crm/reports.html`): new `static/css/reports.css` — `.rpt-period` segmented switcher in topbar, `.rpt-kpi` cards (won value/count, quotes count, team target), `.rpt-rep-row` by-salesperson table, `.rpt-bars` monthly bars + `.rpt-funnel-row` by-channel bars (widths normalized by a tiny inline JS, no deps), `.rpt-mini-row` lost-by-reason. Excel export link unchanged.
- [x] **Settings** (`tenants/settings_*.html` + `_settings_nav.html`): new `static/css/settings.css` — `_settings_nav.html` rebuilt as a `.set-sub` left rail (sectioned, active border); pages use `.set-page-head` + `.set-layout` (230px rail + `.set-main`); hub uses `.set-hub-card` grid; numbering warning → `.set-notice.warn`; LINE webhook → `.set-codeblock`; billing tiers keep their card grid. Pipeline SortableJS reorder + all forms/htmx unchanged.
- [x] **Inbox** — already ported in an earlier pass (`static/css/inbox.css`, 3-pane `.inbox` / `.il-row` thread list / `.chat-stream` bubbles / sage `.inbox-rail` AI suggestions + extracted-lead + make-quote button); left as-is this round (checkbox-on-bubble + tone-pill features in the deck have no backend).
- [x] **Lead detail** (`crm/lead_detail.html` + `crm/_ai_reply.html`): new `static/css/lead.css` — `.ld-hero` (avatar · channel chip · status chip · assigned-to), 2-col `.ld-body` (conversation/activity timeline with the lead's first message as a `.tl-event` + `_activity_list.html` `.tl-*` timeline, sage AI panel: ร่างข้อความ + ร่างใบเสนอราคาด้วย AI htmx flows | `.ld-card` lead facts grid). `_ai_reply.html` rebuilt to the deck's sage `.ai-suggest` card (now a generic primitive in `app.css`: `.ai-suggest` / `-label` / `-text` / `-actions`). All htmx (`crm:lead_suggest_reply`, `crm:lead_send_line_reply`) + convert/AI-quote flows unchanged.
- [x] **Form pages** (`crm/lead_form.html crm/deal_form.html crm/customer_form.html catalog/product_form.html catalog/category_form.html quotes/quotation_form.html` + `registration/password_change_form.html`): new `static/css/forms.css` — `.form-page` wrapper + `.form-page-head` (eyebrow / title / sub) + `.form-card` (styled `.field` inputs with focus ring, `.field-help` / `.field-error` / `.has-error`) + `.form-actions` bar. `partials/_form.html` now emits `.has-error` on the field wrapper and `.field-help` / `.field-error` classes.
- [x] **Onboarding wizard** (`tenants/onboarding.html` + `onboarding/step*.html`): new `static/css/onboarding.css` — top `.ob-progress` bar (width via `widthratio step 5`) + `.ob-pills` step chips, `.ob-layout` (form | `.ob-checklist` side rail with done/active states), step cards switched to `.form-card` + `.sec-label`. `_nav.html` footer (ย้อนกลับ / ข้ามขั้นนี้ / ต่อไป) unchanged.
- [x] **Public pages** (`catalog/public_catalog.html`, `catalog/public_product.html`, `crm/intake.html`, `crm/intake_thanks.html`): `.mark` now shows the tenant's initial (Fraunces) and links back to the showroom; `public.css` got `a.pub-prod:hover` lift + `.pub-prod` as proper block link + mark-as-anchor styling; `intake.html` rebuilt to the deck's "เล่าให้ฟังหน่อย" copy and uses the shared `_form.html`. `public_home.html` / `public_quotation.html` / `_match_results.html` were already deck-aligned (sage match-results block, persimmon CTAs) — left as-is.
- [x] Login / signup / password-reset templates verified — already on `auth.css` / `auth_base.html`, consistent; `password_change_form.html` moved onto `forms.css`.
- [ ] Still rough: pixel polish vs the deck across the board; the deck's quote-editor AI sanity-check rail / grouped-room editor and the inbox tone-pills/message-selection are deck-only (no backend); the lead page has no AI-customer-summary card (no backend); `public_home` has no URL route yet (template exists, served only if a route is added) so the `.mark` links target `public_catalog`; form pages don't use the deck's two-column `.form-grid` (forms render single-column from `_form.html`).

215 tests still green; `manage.py check` + `collectstatic` clean. New CSS this round: `lead.css`, `forms.css`, `onboarding.css` (+ `.ai-suggest` primitive added to `app.css`). Prior: `dashboard.css`, `kanban.css`, `lists.css`, `quote-editor.css`, `deal.css`, `customer.css`, `reports.css`, `settings.css`, `inbox.css`.

---

## M8 — background tasks + LINE inbound depth + small wiring  *(done)*

- [x] **Background-task the slow quotation work** (CLAUDE.md §4.5). `config/settings/base.py`: real `TASKS = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}` (Django 6.0 core ships only `ImmediateBackend` — runs the task **synchronously inside `.enqueue()`**; `django-tasks` PyPI / Celery / RQ is a config-only swap later, no call-site changes). New `apps/quotes/tasks.py`: `@task render_and_email_quotation(doc_id, tenant_id, *, recipient_email, recipient_name, public_url)` (renders PDF to warm-up, then `send_mail` the link) + `@task send_quotation_via_line(doc_id, tenant_id, *, recipient, doc_number, …, log_to_conversation_id, sender_user_id)` (pushes the Flex card via `apps.integrations.line.push_quotation_flex`, logs an outbound `Message` on the source thread). New `apps/integrations/tasks.py`: `@task enrich_conversation_display_name(conversation_id, tenant_id)` (see below). Each task activates `tenant_context(Tenant.objects.get(pk=tenant_id))` first. `apps/quotes/views.py::quotation_send` / `quotation_send_line` now do the fast bits synchronously (share link, `_finalize_sent`, status, "กำลังส่ง…" flash) then `.enqueue()` the slow part; `quotation_send_line` keeps a cheap synchronous `line_is_configured()` gate so it doesn't mark a quote SENT when the tenant has no LINE OA. `conversation_make_quote` left synchronous (interactive AI draft the user is waiting on — §4.5 is about fire-and-forget work).
- [x] **Non-text LINE inbound.** `apps/integrations/line.py::process_line_events` now handles image/sticker/file/video/audio/location (`linebot.v3.webhooks` content types) → records a `Message` with the right `MessageKind` + a Thai placeholder (`[รูปภาพ]`, `[สติกเกอร์]`, `[ไฟล์] <name>`, `[ตำแหน่ง] <title/address>`, …) + `external_id` = the LINE message id; no media bytes downloaded (no media storage yet). Conversation preview updated via `_append_message(kind=…)`; `_conversation.html` renders non-text bubbles italicised. Text still mirrors onto the lead's Activity timeline; non-text doesn't.
- [x] **LINE profile-name enrichment.** `apps/integrations/line.py::fetch_line_profile_name(line_user_id)` (best-effort `MessagingApi.get_profile`, returns "" if LINE unconfigured / API errors). `enrich_conversation_display_name` task uses it to set `Conversation.display_name` (and `lead.name` if it's still the auto `"ลูกค้า LINE ……"` placeholder); enqueued from `get_or_create_conversation` only on newly-created conversations. Guarded — never 500s the webhook. (Tests stub `fetch_line_profile_name` via an autouse fixture in `apps/integrations/tests/conftest.py` so the suite never touches the real LINE API.)
- [x] **Category drag-reorder.** `apps/catalog`: `catalog:category_reorder` (POST, repeated `category=<pk>` in new order → renumbers `ProductCategory.order`); `templates/catalog/categories.html` got a SortableJS drag handle per row (same pattern as the pipeline reorder).
- [x] **`public_home` named URL.** `config/urls.py`: `path("c/<slug:tenant_slug>/home/", catalog_views.public_home, name="public_home")`; the public catalog/product `.mark`/brand links now point at `{% url 'public_home' tenant.slug %}` (the bare `/` on a tenant host still renders it via `core.views.home`).
- [x] **AI customer-summary in the inbox rail.** `apps/integrations/ai.py::summarize_conversation(transcript, *, customer_name="")` (lazy `anthropic`, guarded by `ai_is_configured()`, degrades like the others — 2-3 sentence Thai summary). New endpoint `integrations:conversation_ai_summary` (POST) + `templates/integrations/_ai_summary.html` (sage `.ai-suggest` block, "ผู้ช่วยสรุป — ตรวจก่อนใช้"). Inbox right rail (`templates/integrations/inbox.html`) got a "สรุปลูกค้า" button (`hx-post` → swaps `#ai-summary`). No API key → "ยังไม่ได้ตั้งค่าผู้ช่วย AI".
- [x] Tests added: image-event → IMAGE Message; profile enrichment sets names; AI-summary AI-off path; category reorder updates `order`; `send_quotation_via_line` task pushes + logs; `render_and_email_quotation` task sends mail; `quotation_send_line` still records the outbound Message + marks SENT (existing tests updated: they now create a `LineIntegration` and monkeypatch `apps.integrations.line.push_quotation_flex` since the push happens inside the task). **221 tests green; `manage.py check` clean; `ruff`/`mypy` clean; `makemigrations --check` → "No changes detected".**

> **ImmediateBackend caveat:** `.enqueue()` currently runs the task body synchronously inside the request — so the request isn't actually faster yet; it's the *structure* that's in place (call sites, tenant-context activation, args by id not object). Switching to a durable worker (`django-tasks` DB backend / Celery / RQ) is a `TASKS` setting change with no code changes.

### Still deferred (Phase 1.5+ / deck-only)
Billing / tax invoices / receipts / AR (Phase 2), accounting (Phase 3), email inbound/outbound channel, Stripe/subscriptions — all explicitly post-launch. Deck-only UI with no backend: quote-editor AI sanity-check rail + grouped-room editor, inbox tone-pills / message-selection, Alpine live row-math in the quote editor, AI catalog import-from-URL/PDF, pixel-level deck polish. Customer-360 ↔ conversation linking on the deal page; surfacing "เปิด N ครั้ง" into AI next-step suggestions. Media download/storage for non-text LINE messages.
