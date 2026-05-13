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
- [ ] Self-host Sarabun/IBM Plex Thai fonts in `static/fonts/` (also needed by the WeasyPrint PDF — see CLAUDE.md §7). Fonts still loaded via Google CDN in base/auth templates.
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
- [x] PWA: `static/manifest.json` (theme `#C8501F`, paper bg, standalone) + `static/sw.js` (cache-first for `/static/`) + `<link rel="manifest">` / `theme-color` meta / SW registration in `base.html`. (No app icons yet — manifest `icons: []`.)
- [x] **`make check` green** — ruff + mypy + 199 tests all pass; `collectstatic` works.
- [ ] App icon PNGs (192/512) for the manifest; offline fallback page in the SW.
- [ ] Self-host fonts (still M0-leftover) — also unblocks the WeasyPrint PDF's Thai font (currently relies on a system font).

---

## Status — Phase-1 MVP build complete (M0–M5)

All deck screens rebuilt; LINE inbox + Quote-from-Chat + Flex out; onboarding, settings, public homepage; mobile/PWA baseline. `make check` green. Open follow-ups are tracked as unchecked `[ ]` items under each milestone above — notably: background-tasking PDF/LINE sends (CLAUDE.md §4.5), LINE profile enrichment + non-text inbound, AI customer-summary in the inbox rail, AI catalog-match endpoint on the public home, categories management + bulk catalog actions + AI catalog import, Alpine live quote-line math, surfacing "เปิด N ครั้ง" on deal/quote screens, self-hosted Thai fonts + PDF font, app icons, and pixel-polish vs the design deck.

---

## Definition of done (per CLAUDE.md §8) — applies every milestone

`make check` green · new behavior has tests (incl. tenant-leakage test for any new scoped model) · migrations generated + reviewed · no unjustified `# type: ignore`/`noqa`/`all_tenants()` · money is `Decimal` · slow work in a background task · no per-customer branches (new variability = a setting with a default).
