# salesdee.com · เอกสารแผนสินค้า

**รุ่น 2.2 · 14 พฤษภาคม 2569 (เย็น) · launch-ready · สำหรับ developer · designer · go-to-market**

> เอกสารนี้สรุปการตัดสินใจหลังคุยกับลูกค้าจริง (วัน.ดี.ดี.) · ใช้เป็นแหล่งอ้างอิงเดียวกันก่อนสร้างจริง · ทุก major decision บันทึกที่นี่ · เมื่อสงสัย "ทำไมเลือกแบบนี้" กลับมาดู

> **เปลี่ยนจาก v2.1.1:** PRD sync กับ code state ปัจจุบัน · §12 pricing เปลี่ยนเป็น **Free + 4 tier ที่จ่ายเงิน** (Free / Starter 690 / Growth ⭐ 1,890 / Pro 3,890 / Business 9,900) — เอา Trial 30 วันออก แทนด้วย Free forever · §11 เพิ่ม Feature override + Platform kill switch + Caddy on-demand TLS · §07 stack แทนที่ Celery ด้วย django-q2 · §08 เพิ่ม `Plan` / `BillingCycle` / `Usage` / `TenantFeatureOverride` · §04 / §14 annotate สถานะ built ✓ vs pending ⏳

> **สถานะ build (16 พ.ค. 2569):** Phase 1 Path B shipped ครบ. Phase 1.5 (billing/tax invoice/AR/2FA/audit) shipped. **Path A core flow (quote drawer · multi-step form · source field · requests inbox) shipped ครบ**. สิ่งที่ยังขาด: multi-channel delivery (SendGrid/SMS/DeliveryLog) · theme system 4 แบบ · catalog onboarding 5 paths · Stripe — ดู §14 สำหรับรายละเอียด.

---

## 01 · วิสัยทัศน์

### หนึ่งบรรทัด
**salesdee.** ทำให้ SME ไทยรับ + ออกใบเสนอราคาเร็วและสม่ำเสมอ · ผ่าน 2 channel ที่ลูกค้าใช้จริง: **website ของร้าน** และ **LINE chat**

### ปัญหาที่แก้
SME ไทยมีปัญหา 2 แบบในการรับลูกค้าและออกใบเสนอ:

1. **ลูกค้าใหม่ที่หาผ่าน Google / referral** — เข้าเว็บร้าน แต่ขอใบเสนอยาก ต้องอีเมล/โทรหาเซลส์ · เซลส์ตอบช้า · ลูกค้าหายไป
2. **ลูกค้าที่ทักทาง LINE** — เซลส์รับ chat กระจาย · ทำใบเสนอใน Excel ทุกครั้ง · ใช้เวลา 25-30 นาที · ราคาผิดบ่อย · ดีลตกหาย

### วิธีแก้ของเรา · 2 paths · 1 system

**Path A · Customer self-service บนเว็บ** (เน้น)
- ลูกค้าเข้าเว็บของร้าน · เลือกสินค้า · เพิ่มใน "ใบเสนอ" · กรอกข้อมูล · ส่งคำขอ
- เซลส์ได้รับคำขอ · ตรวจ · ปรับ · ส่งใบเสนอจริงกลับให้ลูกค้า
- ลูกค้าเปิดดู · ยอมรับออนไลน์
- ใช้เวลาเซลส์ลดเหลือ 3-5 นาที (แค่ตรวจและกดส่ง)

**Path B · LINE → เซลส์สร้าง** (เน้น)
- ลูกค้าทักเข้า LINE Official ของร้าน
- เซลส์เห็นใน inbox · สร้างใบเสนอจาก catalog
- ระบบส่งใบเสนอกลับเข้า LINE (PDF + Flex Message)
- ลูกค้าเปิดดู · ติดตามทุกการกระทำได้

**ที่เสริม:** ผู้ช่วยอัจฉริยะช่วยจับคู่สินค้าใน path B · helpful ไม่ใช่หัวใจของระบบ

### ตำแหน่งในตลาด
- ไม่ใช่ generic CRM ขนาดใหญ่ (HubSpot, Salesforce) — overkill
- ไม่ใช่ e-commerce platform (Shopify, WooCommerce) — focus ผิด (เน้นซื้อ ไม่ใช่ขอใบเสนอ)
- ไม่ใช่ LINE OA Manager — ตื้นเกินไป
- **คือ "Quote-first CRM" สำหรับ SME ไทย** ที่ขายผ่านการ "ขอใบเสนอ + เจรจาก่อนตัดสินใจ" (vertical-first: เริ่มที่เฟอร์นิเจอร์สำนักงาน)

---

## 02 · ลูกค้าหลักและ Persona

### Anchor customer
**บริษัท วัน.ดี.ดี.บิสซิเนส จำกัด** — ขายเฟอร์นิเจอร์สำนักงาน B2B · ทีม 8 คน · 60% ของ lead มาจาก LINE · 40% มาจากเว็บไซต์/referral · รายได้ปัจจุบัน 20-30M บาท/ปี

### Persona 1 · ลูกค้า (สำคัญที่สุดในรุ่นนี้)
"คุณนริศ" · ฝ่ายจัดซื้อบริษัทขนาดกลาง
- ต้องการปรับปรุงออฟฟิศ · ค้นหาผู้ขายเฟอร์นิเจอร์ใน Google
- เข้าเว็บไซต์ของวัน.ดี.ดี. · ดูสินค้า · อยากขอใบเสนอเร็ว ๆ
- ไม่อยาก add LINE · ไม่อยากโทร · อยากได้ใบเสนอเป็น PDF ภายใน 1 วัน
- **pain ใหญ่:** หลายเว็บให้ "โทรหา" หรือ "อีเมล hello@..." → ช้าและไม่เป็นมืออาชีพ
- **ความสำเร็จ:** ขอใบเสนอ 3 ผู้ขายภายในชั่วโมงเดียว · เปรียบเทียบและตัดสินใจได้

### Persona 2 · เซลส์ของร้าน (พี่มะลิ)
- หญิง 32 ปี · 8 ปีในวงการ
- ทำงาน 9-18 น. + ตอบ LINE จนถึง 22 น.
- ใช้มือถือ 70% · เดสก์ท็อปตอนทำใบเสนอ
- **pain ใหญ่:** ทำใบเสนอใน Excel ซ้ำ ๆ · จำราคาไม่ได้ · กลัวลืม follow up
- **ความสำเร็จ:** ได้รับคำขอจากเว็บแล้วเปลี่ยนเป็นใบเสนอใน 3 นาที · ตอบ LINE ทันใจ

### Persona 3 · เจ้าของร้าน (พี่สมชาย)
- ชาย 48 ปี · ก่อตั้งบริษัท 12 ปี
- เห็นภาพรวม · ตัดสินใจขั้นใหญ่
- **pain ใหญ่:** ไม่รู้ว่าทีมเซลส์ค้าง deal อะไร · เว็บเดิมไม่มี analytic
- **ความสำเร็จ:** เปิดมือถือเช้ามาเห็นยอดเดือนนี้ · เห็นคำขอใบเสนอใหม่ 5 รายการ

### Persona 4 · admin (น้องปลา)
- ดูแลสต๊อก + ออกใบกำกับภาษี + ออกใบเสร็จ
- รับใบเสนอที่ปิดแล้ว → ทำเอกสารต่อ
- **ความสำเร็จ:** ทุกใบเสนอสม่ำเสมอ · export เข้าระบบบัญชีได้

---

## 03 · User Journeys

**Path A · Customer self-service (เน้น):** ลูกค้าเข้าเว็บ → เลือกสินค้า → quote drawer → กรอก contact/project info → ส่งคำขอ (REQ-NNNN) → เซลส์ได้รับ notification → ตรวจ/ปรับ → ส่งใบเสนอ (email + LINE) → ลูกค้ายอมรับออนไลน์. **เป้าหมาย:** ลูกค้าส่งคำขอ 2 นาที · เซลส์ตอบ 5 นาที. Sales review เสมอ — ไม่มี auto-quote ใน phase นี้.

**Path B · LINE → เซลส์สร้าง (เน้น):** ลูกค้าทัก LINE OA → เซลส์เห็นใน inbox → [ทางเลือก] AI จับคู่สินค้า → quote builder → preview → ส่ง LINE Flex + PDF → ติดตามการเปิด. **เป้าหมาย:** 5 นาที (เดิม 25-30 นาที).

**Catalog onboarding:** wizard 5 paths — template / Excel upload / PDF parse / URL parse / มือถือ. **เป้าหมาย:** 30-50 สินค้าใน 10 นาที.

**CRM:** Kanban pipeline · deal detail (timeline · chat · quotes) · AI next-step hint.

**Billing:** ใบเสนอปิด → ออกใบกำกับภาษี → PDF → ส่ง email · AR aging · sales tax report. ✓ shipped.

---

## 04 · ฟีเจอร์เฟส 1 (MVP · 10-12 สัปดาห์)

ระยะเวลา: **10-12 สัปดาห์** (จากเริ่ม code) · ใช้กับวัน.ดี.ดี. + 1-2 ลูกค้านำร่อง

### Must-have · เรียงตาม priority

> ✓ = built · ⏳ = pending · ◐ = partial

**Tier 0 · Enabler**
1. ◐ **Product onboarding flow** — wizard 5 ขั้นมีแล้ว (company → logo → product → team → LINE) · "5 paths to add products" (template / Excel / PDF / URL / มือถือ) = **⏳ ยังไม่ build** (มีแต่ "พิมพ์เอง")
2. ✓ **Catalog management** — list · edit · category · variant · option · bundle · public catalog
3. ✓ **Multi-tenant** — subdomain routing (`<slug>.<APP_DOMAIN>`) · shared schema · `CurrentTenantMiddleware` · RLS (Postgres) · `TenantManager` auto-scope · `TenantDomain` model for custom domains

**Tier 1 · Path A · Website self-service**
4. ◐ **Public website ของแต่ละ tenant** — public_home + public_catalog + public_product มีแล้ว · **theme system 4 แบบ + custom accent color = ⏳ ยังไม่ build**
5. ✓ **Quote builder บนเว็บ** — quote drawer (Alpine `$store.cart`) + multi-step form + submit → status `request`
6. ✓ **Customer quote view** — public_quotation (`/q/<token>/`) · ลูกค้ายอมรับ/ปฏิเสธ/ขอแก้ออนไลน์ได้
7. ✓ **Quote requests inbox** (back-office) — filter chips: requests / from_web / from_line / drafts / sent / accepted

**Tier 1.5 · Multi-channel delivery** (ใช้ทั้ง 2 paths)
8. ◐ **Email** — `send_mail` + PDF attachment + ลิงก์ดูออนไลน์ มีแล้ว · **HTML template + SendGrid + tracking = ⏳**
9. ✓ **LINE Flex Message** — push `push_quotation_flex` เข้า chat · ปุ่ม "ดูใบเสนอ" + "ดาวน์โหลด PDF"
10. ⏳ **SMS** — ยังไม่ build (provider · template · short link)
11. ⏳ **DeliveryLog tracking** — track sent / delivered / opened ต่อ channel (มี `view_count` บน SalesDocument แต่ยังไม่ใช่ multi-channel)

**Tier 2 · Path B · LINE → เซลส์**
12. ✓ **LINE Official Account integration** — webhook (HMAC verify) · `process_line_events` · text + image + sticker + file + location + audio + video · LINE profile name enrichment (background task)
13. ✓ **Unified inbox** — Conversation + Message models · 3-pane (thread list / transcript / AI rail) · assign · close · reopen
14. ✓ **Quote builder ใน back-office** — quote editor (htmx + Alpine live row math) · product picker type-ahead · Quote-from-Chat one-click review-and-send flow
15. ✓ **PDF generator** — WeasyPrint · bundled Sarabun font (no remote fetch) · per-line images

**Tier 3 · CRM พื้นฐาน**
16. ✓ **Customer 360** — profile · contacts · deals · quotations (`view_count` + `last_viewed_at`) · LINE conversations · activity timeline · tasks
17. ✓ **Deal pipeline** — Kanban (SortableJS drag-drop) · per-tenant stages · rule-based AI next-step hint
18. ✓ **Activity timeline** — call · visit · note · email · LINE · stage_changed · quote_sent · quote_viewed · auto-events

**Tier 4 · Pricing + feature gating** (ใหม่ใน v2.2 · ไม่อยู่ใน v2.1.1)
19. ✓ **Plan registry** — `apps/tenants/plans.py` · 4 public tier + Trial 30 วัน · per-tier limits + features (dataclass · single source of truth)
20. ✓ **Usage quotas** — `Usage(TenantScopedModel)` per (tenant, period YYYYMM, kind) · count line_msgs / ai_drafts / tax_invoices · soft-warn ≥80% · hard-block tax_invoices ที่ cap
21. ✓ **Billing module gate** — `BillingFeatureGateMiddleware` `/billing/*` → 402 + upgrade page เมื่อ plan ไม่รวม
22. ✓ **TenantFeatureOverride** — platform admin override ต่อ tenant (FORCE_ON / FORCE_OFF · expires_at) — anchor grant / dispute / beta rollout
23. ✓ **PLATFORM_DISABLED_MODULES** — env-level kill switch (incident handling · win เหนือทั้ง override + plan)
24. ✓ **`/settings/modules/`** — read-only inventory (owner/manager only · KPI strip · override badge + reason · platform-off badge)
25. ✓ **Plan change UI** — owner/manager กดเปลี่ยน tier จาก `/settings/billing/` · audit event บันทึก before/after

### Nice-to-have (ทำเมื่อเหลือเวลา)
- ผู้ช่วยจับคู่สินค้า (LINE inbox) — basic AI · ใช้ Claude API
- รายงานพื้นฐาน — ยอดเดือน · funnel · top products
- การเชิญทีม + สิทธิ์ (owner / admin / sales / viewer)

### ไม่มีใน Phase 1
- ใบกำกับภาษี + ใบเสร็จ → Phase 1.5
- รายงานละเอียด → Phase 1.5
- AI workflows เต็มที่ → Phase 2
- Native mobile app → ใช้ PWA แทน
- Marketplace · API ภายนอก → Phase 2

---

## 08 · โครงสร้างฐานข้อมูล

### Key entities

> **หมายเหตุ:** code ใช้ชื่อ `SalesDocument` แทน `Quote` (เพราะ entity เดียวกันรองรับทุกประเภทเอกสาร: quotation / invoice / tax invoice / receipt / credit note / debit note / deposit / sales order / delivery note). field ที่ระบุข้างล่างนี้คือ shape conceptual — ถ้าจะ map ตรง ๆ ดู `apps/quotes/models.SalesDocument`. `Quote` ในเอกสารนี้ = `SalesDocument(doc_type=QUOTATION)`.

```
Tenant (บริษัทที่ใช้ระบบ · global model · ไม่ tenant-scoped)
  ├─ name, slug, is_active
  ├─ plan ("trial" | "starter" | "growth" | "pro" | "business")
  ├─ billing_cycle ("monthly" | "annual")
  ├─ trial_ends_at, subscription_started_at, current_period_ends_at
  ├─ accent_color ⏳ (override สีแบรนด์ · ยังไม่ build)
  └─ website_theme ⏳ ("craft" | "atelier" | "bauhaus" | "velvet" · ยังไม่ build)
  // (LineIntegration เก็บแยกใน apps/integrations · ไม่ inline บน Tenant)

TenantDomain (custom domain · global model)
  ├─ tenant_id, domain (unique)
  ├─ is_primary, verified
  └─ // verified=True → Caddy /_caddy/ask อนุญาตออก TLS cert

Plan (registry · pure-Python · ไม่อยู่ใน DB — apps/tenants/plans.py)
  ├─ code, label_th, tagline_th
  ├─ monthly_thb, annual_thb (Decimal · annual = -17%)
  ├─ limits: users · line_msgs · ai_drafts · tax_invoices · storage_gb · audit_retention_days
  └─ features: billing_module · white_label_pdf · custom_domain · api_access · e_tax_invoice · priority_support · sla

Usage (counter per tenant · period · kind)
  ├─ tenant_id, period (YYYYMM int · Asia/Bangkok)
  ├─ kind ("line_msgs" | "ai_drafts" | "tax_invoices")
  └─ count (PositiveInteger · F-expr atomic increment)
  // unique (tenant, period, kind) · check_quota / increment_usage / gated() ใน apps/tenants/quota.py

TenantFeatureOverride (platform admin override · global model)
  ├─ tenant_id, module_code (billing / e_tax / white_label / ...)
  ├─ mode (FORCE_ON | FORCE_OFF)
  ├─ reason (text · anchor grant · dispute · beta rollout)
  └─ expires_at (nullable · expired rows ถูก ignore โดย feature_enabled)

User (พนักงาน)
  ├─ tenant_id, email, full_name, role (owner/admin/sales/viewer)
  ├─ line_user_id (รับ notification ทาง LINE personal)
  └─ avatar, preferences

Customer (ลูกค้า)
  ├─ tenant_id, name, contact_name, phone, email, company, tax_id
  ├─ line_user_id (ถ้ามาทาง LINE OA)
  ├─ source (website / line / referral / manual)
  ├─ segment, tags
  └─ lifetime_value, last_active_at

Category
  ├─ tenant_id, name, slug, parent_id (tree max 2 levels)
  └─ icon, image, sort_order

Product
  ├─ tenant_id, sku, name, slug, category_id
  ├─ description, specs (jsonb · ขนาด · วัสดุ · มอก.)
  ├─ base_price, cost, variants (jsonb)
  ├─ visibility (public / internal / draft)
  ├─ stock_status, stock_qty
  ├─ tags (jsonb)
  ├─ completeness_score (computed · % ความสมบูรณ์)
  ├─ has_image, has_price (denormalized for filter)
  └─ sales_count, last_sold_at

Conversation (LINE thread)
  ├─ tenant_id, customer_id, line_thread_id
  ├─ status (open / waiting / resolved / archived)
  ├─ assigned_to (user_id)
  ├─ deal_id (link เมื่อมีดีล)
  └─ last_message_preview, unread_count, last_message_at

Message
  ├─ conversation_id, direction (in / out)
  ├─ message_type (text / image / sticker / file / flex / system)
  ├─ text, media_url, flex_payload (jsonb)
  ├─ line_message_id, sent_by_user
  ├─ ai_parsed (jsonb · intent · suggested_products)
  └─ delivered_at, read_at

Deal
  ├─ tenant_id, customer_id, name, value
  ├─ stage (lead / qualified / proposal / negotiate / won / lost)
  ├─ source (website / line / referral / manual)
  ├─ owner (user_id), probability, expected_close_date
  ├─ closed_at, lost_reason
  └─ tags

Quote (★ key entity · มี 2 source · status workflow ใหม่)
  ├─ tenant_id, number (QT-2026-NNNN), deal_id, customer_id
  ├─ source ★ ("website" | "line" | "manual")  ← new
  ├─ customer_snapshot (jsonb · ข้อมูล ณ เวลาออก)
  ├─ items (jsonb · product_id, name, sku, qty, unit_price, line_total)
  ├─ subtotal, discount_pct, discount_amt, tax_pct, tax_amt, total
  ├─ status ("request" | "review" | "draft" | "sent" | "viewed"
  │          | "accepted" | "rejected" | "expired" | "revised")  ← extended
  ├─ valid_until, sent_at, viewed_at, accepted_at
  ├─ public_token (signed · for public quote view URL)
  ├─ view_count, last_viewed_ip
  ├─ terms, internal_notes
  ├─ project_info (jsonb · address · deadline · install · budget_range)  ← new for website-submitted
  └─ created_by (user_id หรือ null ถ้ามาจาก website)

QuoteEvent (audit log)
  ├─ quote_id, event_type (created / submitted / reviewed / sent / viewed
  │                       / accepted / rejected / expired / revised / comment)
  ├─ actor_user (user_id หรือ null)
  ├─ actor_is_customer (bool)
  └─ metadata (jsonb)

DeliveryLog ★ (ติดตามการส่งใบเสนอแต่ละ channel · ใหม่ใน v2.1)
  ├─ tenant_id, quote_id
  ├─ channel ("email" | "line" | "sms")
  ├─ sent_to (email address / line_user_id / phone number)
  ├─ status ("queued" | "sent" | "delivered" | "failed" | "opened" | "clicked")
  ├─ provider ("sendgrid" | "line_api" | "thsms" | "twilio")
  ├─ provider_message_id
  ├─ sent_at, delivered_at, opened_at, clicked_at, failed_at
  ├─ retry_count
  ├─ error_message
  └─ metadata (jsonb · open count · click URL · etc.)

Activity (timeline)
  ├─ tenant_id, deal_id, customer_id, user_id
  ├─ type (call / visit / note / quote_sent / quote_viewed
  │        / message_sent / message_received / stage_changed
  │        / deal_won / deal_lost / quote_requested)  ← new event
  ├─ title, description, metadata
  └─ scheduled_for, completed_at
```

### Quote status workflow

```
website ──→ request → review → sent → viewed ──→ accepted
                          │                  ├──→ rejected
                          └→ draft           └──→ expired

LINE/manual ──→ draft → sent → viewed → (same outcomes)

revised: new Quote inherits parent_quote_id from old one
```

- **Quote.source = "website"** → status เริ่มที่ "request" (ลูกค้าส่งคำขอ · รอเซลส์ตรวจ)
- **Quote.source = "line" / "manual"** → status เริ่มที่ "draft" (เซลส์สร้าง · ยังไม่ส่ง)

---

## 09 · Communication channels

ส่งใบเสนอผ่าน 3 channel · เซลส์เลือกใน send dialog · default จาก context (LINE thread → LINE, เว็บ → email)

| Channel | สถานะ | หมายเหตุ |
|---|---|---|
| **LINE Flex Message** | ✓ built | push via LINE API · HMAC-SHA256 verify webhook |
| **Email + PDF** | ◐ partial | `send_mail` + attachment ทำงาน · HTML template + SendGrid + tracking ⏳ |
| **SMS** | ⏳ future | provider + template + short link ยังไม่ build |

**Send dialog** (⏳ ยังไม่ build): modal เลือก channel · checkbox Email/LINE/SMS · custom message · preview ต่อ channel

**DeliveryLog** (⏳ ยังไม่ build): track sent/delivered/opened ต่อ channel ต่อใบเสนอ

---

## 10 · AI (ตัวเสริม)

**Model:** Claude Sonnet 4.6 (matching/parsing/summarization) · Claude Haiku (task เล็ก)

**ใช้ที่ไหน:**
- ✓ Built: product match จาก LINE text → เสนอ 3 รายการ · reply suggest · customer summary · deal next-step hint
- ⏳ Future: parse PDF/URL spec → catalog fields · column mapping ใน Excel import · suggest category จากรูป

**UX rules (ห้ามเปลี่ยน):** AI ใช้สีเซจเสมอ · AI เสนอเท่านั้น เซลส์ตัดสิน · ห้าม AI กระทำเงียบ · fallback gracefully ถ้า API ล่ม

**Cost guardrails:** rate limit/tenant · cache 24h · quota ต่อ tier (`ai_drafts`) · fail open (quota error ไม่ block workflow)

---

## 11 · Multi-tenant

**โมเดล:** shared database, ทุก tenant มีข้อมูลแยกกันสมบูรณ์ ไม่มีทางรั่วไหลข้ามกัน

**URL ของแต่ละ tenant:**
- Built-in: `<slug>.salesdee.app` (ทุก tier)
- Custom domain: `wandeedee.com` (tier Pro+ เท่านั้น) — tenant ชี้ CNAME มาที่ app, ระบบออก TLS cert อัตโนมัติ
- Platform: `salesdee.app` / `app.salesdee.app` → marketing + login (ไม่ใช่ tenant)

**Feature gating (3 ชั้น · ชั้นแรกชนะ):**
1. **Platform kill switch** — ปิดทั้งระบบ ใช้ตอน incident/maintenance
2. **Per-tenant override** — FORCE_ON (anchor grant / beta) หรือ FORCE_OFF (dispute) · กำหนดวันหมดอายุได้
3. **Plan features** (default) — billing · white-label PDF · custom domain · API · e-Tax invoice · priority support · SLA

**Usage quotas (นับต่อเดือน):** ไลน์ msg · AI draft · ใบกำกับภาษี — soft warn ≥80% · hard-block เฉพาะใบกำกับภาษีที่เกิน cap · ไม่ block LINE inbound (UX ห้ามพัง)

**Security:** ข้อมูลแต่ละ tenant ไม่รั่วไปอีก tenant · audit log ทุก state change สำคัญ · 2FA TOTP opt-in · per-tenant LINE token เข้ารหัสใน DB

---

## 12 · ราคา (v2.2 · เปลี่ยนจาก v2.1.1)

### 5 tier (Free + 4 paid) — `apps/tenants/plans.py`

| Tier | ราคา/เดือน | รายปี (-17%) | Users | ไลน์ msg/เดือน | เอไอ draft | ใบกำกับภาษี | สำหรับ |
|------|-----------|-------------|-------|---------------|----------|------------|--------|
| **Free** | 0 | — | 1 | 100 | 10 | — | ทดลองทุกฟีเจอร์หลัก · ไม่ตัดบัตร · ใช้ได้ตลอด |
| **Starter** | 690 | 6,900 | 2 | 500 | 30 | — | ทีมเล็ก 1-3 คน · ขยับจาก Excel |
| **Growth ⭐** | 1,890 | 18,900 | 5 | 3,000 | 200 | — | ทีมขาย 3-5 คน · ปิดดีลเร็วผ่านไลน์ |
| **Pro** | 3,890 | 38,900 | 12 | 10,000 | 800 | 500 | บริษัทกลาง 5-12 คน · ใบกำกับภาษี + ลูกหนี้ครบ |
| **Business** | 9,900 | 99,000 | ∞ | ∞ | ∞ | ∞ | บริษัทใหญ่ · หลายสาขา · 5 ปี audit |

### Tier features

| Feature | Free | Starter | Growth ⭐ | Pro | Business |
|---|:---:|:---:|:---:|:---:|:---:|
| ใบเสนอราคา (Quote) | ✓ | ✓ | ✓ | ✓ | ✓ |
| ไลน์ OA + Quote-from-Chat + AI helpers | ✓ | ✓ | ✓ | ✓ | ✓ |
| White-label PDF (ลบ "powered by salesdee.") | — | — | ✓ | ✓ | ✓ |
| ระบบบัญชี (ใบกำกับภาษี · ใบเสร็จ · CN/DN · AR · ใบแจ้งยอด) | — | — | — | ✓ | ✓ |
| โดเมนของตัวเอง (custom domain + auto TLS) | — | — | — | ✓ | ✓ |
| API + webhook | — | — | — | อ่าน | อ่าน + เขียน |
| Priority support | — | — | — | ✓ | ✓ |
| ใบกำกับภาษีอิเล็กทรอนิกส์ (e-Tax) | — | — | — | — | ✓ |
| SLA 99.5% + onboarding 1 ต่อ 1 | — | — | — | — | ✓ |
| Audit retention | 14 วัน | 30 วัน | 90 วัน | 1 ปี | 5 ปี (PDPA) |

### Enforcement (ทำงานจริงใน code)

- `BillingFeatureGateMiddleware` → `/billing/*` คืน 402 + upgrade page เมื่อ plan ไม่รวม `billing_module`
- `gated(tenant, "ai_drafts")` context-manager → AI calls ดึงจาก `Plan.limits.ai_drafts` · soft-warn ที่ 80% · skip ที่ cap
- `enforce_quota(tenant, "tax_invoices")` ใน `issue_tax_invoice` → raise `QuotaExceeded` ที่ cap · view คืน 402
- LINE msg inbound bump `Usage(kind="line_msgs")` · ไม่ block (ห้ามเสีย customer UX) · soft-warn ที่ 80%
- Member invite → check `Plan.limits.users` · refuse + flash ถ้าเกิน

### กลยุทธ์เริ่มต้น
- **Free** = forever tier · powered-by salesdee. แสดงบนใบเสนอ · ใช้ลองและเล็กน้อยได้ตลอด · ไม่กดดันให้ upgrade
- **วัน.ดี.ดี. (anchor)** = `TenantFeatureOverride(billing, FORCE_ON, expires=6m)` บน Free → ใช้ทุกอย่างฟรี 6 เดือนแลก case study
- **First-10 paying** = 50% off ปีแรกบน annual plan (lock-in)
- ทำ Stripe ทีหลัง — Phase D · ใช้ manual invoice + bank transfer ก่อน
- ราคารายปี = -17% (2 เดือนฟรี)

### Add-ons (across tiers · planned · ยังไม่ build)
- LINE msg pack: 1,000 = +300 ฿/เดือน
- AI draft pack: 500 = +500 ฿/เดือน
- Extra user (Starter/Growth/Pro): +290 ฿/user/เดือน
- e-Tax invoice module: +990 ฿/เดือน (Pro), included Business
- Onboarding 1-1: 4,900 ฿ one-time

---

## 13 · Success metrics

### Phase 1 (เปิดตัวกับวัน.ดี.ดี.)

**Activation**
- ใส่ catalog ครบ 30+ สินค้าใน 7 วันแรก
- เซลส์ทั้ง 3 คน login ทุกวัน
- ติดตั้ง LINE webhook สำเร็จใน 1 ชม

**Path A · website**
- **คำขอใบเสนอจากเว็บ ≥ 5/สัปดาห์** ใน 4 สัปดาห์แรก
- Conversion rate (visit → quote request) ≥ 3%
- เวลาเซลส์ตอบคำขอ ≤ 1 วันทำการ

**Path B · LINE**
- ใบเสนอผ่าน LINE flow ≤ 5 นาที (เดิม 25-30)
- LINE Flex message delivery rate ≥ 98%

**Outcome**
- จำนวนใบเสนอที่ออก/สัปดาห์ × 3 เทียบกับก่อนใช้
- Win rate ≥ 60% (เดิม ~45%)
- 0 ดีลตกหายในเดือนแรก

### Phase 1.5 (3-6 เดือนหลังเปิดตัว)
- 10 paying tenants
- Net Revenue Retention > 100%
- NPS > 50 จาก paying tenants
- ใบเสนอที่ออกผ่านระบบ ≥ 70% มาจาก website self-service (path A เป็นหลัก)

### Phase 2 (12 เดือน)
- 100 paying tenants
- MRR 500,000 บาท/เดือน
- Vertical 2 เปิดตัว (TBD)

---

## 14 · Roadmap · status ณ 14 พ.ค. 2569

### ✓ Shipped (Phase 1 + Phase 1.5 + pricing layer)
- multi-tenant + auth + RLS + middleware (M0–M2)
- LINE inbox (Conversation/Message · webhook · profile enrichment · non-text inbound)
- Quote-from-Chat → AI draft → one-click review-and-send → LINE Flex back into thread
- Back-office quote builder (htmx + Alpine live row math + product type-ahead)
- WeasyPrint PDF (bundled Sarabun · no remote fetch)
- CRM (customer 360 · deal Kanban · activity timeline · rule-based AI next-step)
- public catalog + product + showroom + intake form + sticky mobile CTA
- onboarding wizard 5-step (M4)
- per-tenant settings (company · LINE · pipeline · numbering · members · billing · audit · 2FA)
- system status page + module status inventory
- Phase 1.5 billing: invoice · tax invoice (ม.86/4) · receipt · CN · DN · payment · AR aging · sales tax report · customer statement · send via email/LINE
- audit log (`AuditEvent` + RLS)
- notifications (daily digest · quote-viewed ping · AR reminders) via django-q2
- 2FA TOTP per-user opt-in
- deploy infra: django-q2 (replace `django.tasks`) · split `Q_REDIS_URL` / `CACHE_REDIS_URL` · Cloudflare R2 · gunicorn==23 · VPS_DEPLOYMENT.md
- **pricing v2.2:** plan registry · Usage quotas · billing module gate · TenantFeatureOverride · PLATFORM_DISABLED_MODULES kill switch · `/settings/modules/` inventory
- Caddy on-demand TLS + `/_caddy/ask` endpoint · `tls internal` (dev) → ACME (prod) ready
- `./dev.sh` runner (django + qcluster + caddy + migrate + sudo cache)

### ✓ Shipped (Path A — เพิ่มเติม 16 พ.ค. 2569)
- Quote drawer บน tenant website (Alpine `$store.cart` · `tenant-site.js`)
- Multi-step quote request form (`/c/<slug>/request/`)
- `SalesDocument.source` field (`website / line / manual`) + status `request`
- Quote Requests inbox — filter chips ใน quotation_list (requests / from_web / from_line)

### ⏳ Pending — Multi-channel delivery
5. **HTML email template + SendGrid** (ปัจจุบันใช้ console + plain attachment)
6. **SMS channel** — provider + template + short link + opt-in
7. **`DeliveryLog` entity** — track sent/delivered/opened ต่อ channel
8. **Send dialog UI** — multi-check + preview ต่อ channel

### ⏳ Pending — Tenant themes
9. **Theme system 4 แบบ** (craft / atelier / bauhaus / velvet) — CSS variable swap + per-tenant `Tenant.theme` field
10. **Accent color override** — picker ใน settings → CSS variable injection
11. **Per-tenant logo** บน public site (มี logo upload แล้ว · เพิ่ม binding)

### ⏳ Pending — Catalog onboarding (Tier 0)
12. **5 paths to add products**: template (preset packs) · Excel import (column map) · PDF spec parse (AI vision) · URL parse · mobile photo+form
13. **`Product.completeness_score`** + filter ขาดรูป/ราคา

### ⏳ Pending — Misc
14. **Real async backend** — ปัจจุบัน TASKS ใช้ `ImmediateBackend` (sync ใน request) · switch ไป django-q2 backend ใน TASKS = config-only
15. **Trial expiry enforcement** (Phase C) — auto-set `trial_ends_at` ตอน signup · daily cmd `expire_trials` · grace 7 วัน → read-only · banner countdown
16. **Stripe subscription** (Phase D) — currently manual invoice + bank transfer
17. **Per-tenant Anthropic API key** (Business tier)
18. **Programmatic SEO** (JSON-LD `schema.org/Product` · sitemap.xml · OG tags)
19. **Time-to-quote / first-response metrics** on `/crm/reports/`

### Decision points coming up
- Theme system ทำเป็น preset 4 ตัว หรือ tenant pick accent + font?
- Custom domain provisioning UI (วันนี้ผ่าน Django admin) ขึ้นเป็น settings page ตอนไหน?

---

## 15 · ความเสี่ยง

### Technical
- **LINE API rate limit** เมื่อ tenant เยอะ — message queue ตั้งแต่แรก
- **AI cost runaway** — guardrails (rate · cache · tier budget)
- **Multi-tenant data leak** — testing เข้มข้น · audit log
- **PDF rendering slow** — async ผ่าน django-q2 · cache PDF ที่ render แล้ว
- **Quote request spam** จาก website — rate limit + reCAPTCHA + email verify

### Product
- **Onboarding ยากไป** — ลูกค้า drop ก่อนถึง first quote — UX test ละเอียด · template ครบ
- **Customer self-service ไม่ pop** — ลูกค้าไม่ใช้เว็บ ใช้ LINE หมด — ยอมรับและพึ่ง path B · iterate UX
- **AI accuracy แย่** — product match ผิด — เซลส์ตรวจก่อนเสมอ · ใช้ confidence score · feedback loop
- **LINE platform dependency** — fallback ผ่าน email · web form
- **Vertical-fit** — เริ่มที่เฟอร์นิเจอร์อาจไม่กว้างพอ — Vertical 2 ก่อน 6 เดือน

### Business
- **Anchor customer dependence** — case study + 1-2 ลูกค้ารองก่อน vit
- **Competitor (LINE OA Manager · HubSpot · WooCommerce + plugin)** — focus 10x ของเรา: vertical + Thai + LINE-first + quote-as-primary
- **PDPA compliance** — privacy policy · data export · DPA สำหรับ Business tier
- **ลูกค้ามองว่าราคาแพง** เทียบกับ "ใช้ Google Form ก็ได้" — show ROI ชัด · case study

---

## 16 · Open questions

1. **Stripe vs Omise** — เริ่ม Stripe + bank transfer ไปก่อน · ใส่ Omise เมื่อมีลูกค้าขอ
2. **Theme system** — preset 4 แบบ หรือ tenant pick accent + font เอง?
3. **Custom domain provisioning UI** — ตอนนี้ผ่าน Django admin · ขึ้น settings page ตอนไหน?

---

## 17 · Design files

| ไฟล์ | คอนเทนต์ | สถานะ |
|------|----------|--------|
| `design/brand-guide.html` | palette · type · tokens · `.ic` icons · logo | ✓ reference เสมอ |
| `design/backoffice.html` | 27 frames back-office | ✓ ทุก frame built แล้ว |
| `design/tenant-site.html` | 12 frames tenant site + theme switcher | ✓ built (ยกเว้น ts-toggle/ts-panel = theme ⏳) |
| `design/website.html` | salesdee.com marketing site | ⏳ ยังไม่ build เลย |

*v2.3 · 16 พ.ค. 2569 · sync กับ code state*
