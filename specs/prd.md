# salesdee.com · เอกสารแผนสินค้า

**รุ่น 2.2 · 14 พฤษภาคม 2569 (เย็น) · launch-ready · สำหรับ developer · designer · go-to-market**

> เอกสารนี้สรุปการตัดสินใจหลังคุยกับลูกค้าจริง (วัน.ดี.ดี.) · ใช้เป็นแหล่งอ้างอิงเดียวกันก่อนสร้างจริง · ทุก major decision บันทึกที่นี่ · เมื่อสงสัย "ทำไมเลือกแบบนี้" กลับมาดู

> **เปลี่ยนจาก v2.1.1:** PRD sync กับ code state ปัจจุบัน · §12 pricing เปลี่ยนเป็น **Free + 4 tier ที่จ่ายเงิน** (Free / Starter 690 / Growth ⭐ 1,890 / Pro 3,890 / Business 9,900) — เอา Trial 30 วันออก แทนด้วย Free forever · §11 เพิ่ม Feature override + Platform kill switch + Caddy on-demand TLS · §07 stack แทนที่ Celery ด้วย django-q2 · §08 เพิ่ม `Plan` / `BillingCycle` / `Usage` / `TenantFeatureOverride` · §04 / §14 annotate สถานะ built ✓ vs pending ⏳

> **สถานะ build (14 พ.ค. 2569):** Phase 1 Path B (LINE → เซลส์) shipped ครบ. Phase 1.5 (billing / ใบกำกับภาษี / AR / 2FA / audit) shipped. **Path A (customer self-service บนเว็บ) + multi-channel delivery (Email/SMS template + DeliveryLog) + theme system 4 แบบ = ยังไม่ build** — ดู §04 และ §14 สำหรับรายละเอียด.

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

## 03 · User Journey · 5 หลัก (เรียงตาม priority ใหม่)

### Journey 1 · Customer self-service quote (Path A · เน้น)
```
ลูกค้าเปิดเว็บของร้าน (wandeedee.com / wandeedee.salesdee.app)
  ↓
เลือกสินค้า → กด "เพิ่มในใบเสนอ"
  ↓
ดู quote drawer · ปรับจำนวน · ลบ
  ↓
กด "ขอใบเสนอราคา" → เปิดฟอร์ม multi-step
  ↓
Step 1: ตรวจรายการ
Step 2: ข้อมูลผู้ติดต่อ (ชื่อ · บริษัท · เบอร์ · email · LINE ID)
Step 3: รายละเอียดโปรเจกต์ (ที่อยู่ส่ง · เวลา · ต้องการติดตั้ง?)
Step 4: ยืนยัน + ส่ง
  ↓
สำเร็จ → เลขที่คำขอ "REQ-2026-NNNN" · "ทีมจะติดต่อใน 1 วันทำการ"
  ↓
[ใน back-office] เซลส์ได้รับ notification · เปิดคำขอใน Quote Requests Inbox
  ↓
ตรวจ stock · ปรับราคา · ใส่ส่วนลด volume · ใส่ค่าติดตั้ง · เงื่อนไขชำระ
  ↓
กด "ส่งใบเสนอ" → เลือกช่องทาง:
  ☑ Email + PDF (default · ถ้ามีอีเมล)
  ☑ LINE Flex Message (ถ้ามี LINE ID)
  ☐ SMS (sms + ลิงก์ดูออนไลน์)
  ↓
ส่งครั้งเดียว · ทุก channel ที่เลือก
  ↓
ลูกค้าเปิดดูจาก channel ไหนก็ได้ (track delivery + open ต่อ channel)
  ↓
กดยอมรับออนไลน์
```

**เป้าหมาย:** ลูกค้าส่งคำขอใน 2 นาที · เซลส์ออกใบเสนอจริงใน 5 นาที · ส่งผ่าน channel ลูกค้าเลือก

**Approval model: Path 1 — Sales review เสมอ**
- ทุกคำขอจากเว็บผ่านการ review ก่อนส่ง · ราคาแม่นตรงสถานการณ์
- ในอนาคต (Phase 1.5) อาจเพิ่มทาง "Auto-quote" สำหรับสินค้าที่ราคาคงที่ · ไม่ใช่ภาระเซลส์

### Journey 2 · LINE → เซลส์สร้าง (Path B · เน้น)
```
ลูกค้าทัก LINE Official ของร้าน
  ↓
เซลส์เห็นใน inbox · เปิดอ่าน
  ↓
[ทางเลือก] กด "ผู้ช่วยจับคู่สินค้า" → AI เสนอ 3 รายการ
  ↓
เซลส์เปิด quote builder · เลือกสินค้า + ใส่จำนวน · ส่วนลด · เงื่อนไข
  ↓
preview PDF + LINE Flex Message
  ↓
กด "ส่ง" → เลือกช่องทาง (LINE default · Email · SMS เพิ่ม)
  ↓
ลูกค้าได้รับใน channel ที่เลือก
  ↓
ติดตาม: ลูกค้าเปิดเมื่อใด · กี่ครั้ง · ต่อ channel · ใกล้หมดอายุเตือน
```

**เป้าหมาย:** เซลส์ทำใบเสนอจากแชต LINE ใน 5 นาที (เดิม 25-30 นาที)

### Journey 3 · Product onboarding (Path 4 · enabler)
```
Tenant ใหม่ login ครั้งแรก → catalog 0 items
  ↓
เลือก 1 จาก 5 paths:
  - Template (30-50 สินค้าตัวอย่าง · 5 นาที)
  - Excel upload (100+ items · 10 นาที)
  - PDF spec sheet (AI parse · 2 นาที/ไฟล์)
  - URL ผู้ผลิต (AI parse · 30 วินาที/URL)
  - ถ่ายรูป + กรอก (มือถือ · 1 นาที/ชิ้น)
  ↓
catalog เห็นความก้าวหน้า "82% สมบูรณ์" · banner ฉลอง
  ↓
รายการที่ขาดข้อมูล (รูป · ราคา) มี badge · เติมทีหลังได้
  ↓
ผู้ช่วยเสนอ "ราคาเฉลี่ยในหมวด" · เซลส์ตรวจและตัดสิน
```

**เป้าหมาย:** ใส่ catalog ครั้งแรก 30-50 สินค้าใน 10 นาที · พร้อมใช้ทั้ง 2 paths

### Journey 4 · จัดการดีล (CRM)
- ดู Kanban ของดีลทั้งหมด (lead · proposal · negotiate · won · lost)
- คลิกดีล → เห็นที่มา (website / LINE) · ประวัติ chat · ใบเสนอที่ส่ง · activity ทั้งหมด
- บันทึก call · visit · note
- ผู้ช่วยแนะนำ "ลูกค้าเปิด 4 ครั้ง · ลองตามตอนนี้"

### Journey 5 · ออกใบกำกับภาษี + ใบเสร็จ (Phase 1.5)
- จากใบเสนอที่ปิด → กด "ออกใบกำกับ"
- ระบบ generate ตาม template
- admin ตรวจ · ส่ง email หรือ download PDF
- export CSV เข้าระบบบัญชี

---

## 04 · ฟีเจอร์เฟส 1 (MVP · 10-12 สัปดาห์)

ระยะเวลา: **10-12 สัปดาห์** (จากเริ่ม code) · ใช้กับวัน.ดี.ดี. + 1-2 ลูกค้านำร่อง

### Must-have · เรียงตาม priority

> ✓ = built · ⏳ = pending · ◐ = partial

**Tier 0 · Enabler**
1. ◐ **Product onboarding flow** — wizard 5 ขั้นมีแล้ว (company → logo → product → team → LINE) · "5 paths to add products" (template / Excel / PDF / URL / มือถือ) = **⏳ ยังไม่ build** (มีแต่ "พิมพ์เอง")
2. ✓ **Catalog management** — list · edit · category · variant · option · bundle · public catalog
3. ✓ **Multi-tenant** — subdomain routing (`<slug>.<APP_DOMAIN>`) · shared schema · `CurrentTenantMiddleware` · RLS (Postgres) · `TenantManager` auto-scope · `TenantDomain` model for custom domains

**Tier 1 · Path A · Website self-service** — ⏳ ทั้งหมด
4. ◐ **Public website ของแต่ละ tenant** — public_home + public_catalog + public_product มีแล้ว · **theme system 4 แบบ + custom accent color = ⏳ ยังไม่ build**
5. ⏳ **Quote builder บนเว็บ** — quote drawer · multi-step form · submit → request (per `specs/furniture-site.html`)
6. ◐ **Customer quote view** — public_quotation มีแล้ว (`/q/<token>/`) · ลูกค้ายอมรับ/ปฏิเสธ/ขอแก้ออนไลน์ได้
7. ⏳ **Quote requests inbox** (back-office) — ปัจจุบันมี LINE inbox เท่านั้น · "Quote Requests" inbox จาก website submissions = ยังไม่ build

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

## 05 · ฟีเจอร์เฟส 1.5 (3-4 เดือนหลังเปิดตัว)

- **ตัวสร้างใบกำกับภาษี + ใบเสร็จ** (รูปแบบกรมสรรพากร)
- **รายงานละเอียด** — funnel · revenue trend · sales rep performance · win rate
- **Email notifications** — daily digest · alert เมื่อลูกค้าเปิดดู · ดีลใกล้หมดอายุ
- **Tasks + reminders** — ตามดีล · นัดประชุม · เตือน
- **Export ข้อมูล** — CSV สำหรับ admin
- **Catalog onboarding ขั้นสูง** — bulk photo + AI tagging · custom field
- **Quote templates** — ของแถม · เงื่อนไขชำระ · template หลายแบบ
- **Customer portal** — ลูกค้าดู order history · ใบเสนอเก่า

---

## 06 · ฟีเจอร์เฟส 2 (6 เดือน+)

- **API integration ภายนอก** — Slack · Email · Google Sheets · ERP (Express, FlowAccount, PEAK)
- **AI workflows** — automation จัดการดีล · auto-draft message · prediction
- **Voice / video** — บันทึก call · transcribe
- **Marketplace** — template + theme หลายแบบ · share ระหว่าง tenants
- **Vertical 2** — เปิดสาย vertical ใหม่ (เครื่องเสียง · vehicle parts · industrial)
- **White-label เต็มที่** — custom domain · ไม่มี salesdee branding (tier Business)

---

## 07 · Tech stack

### Stack เต็ม (ไม่เปลี่ยนจาก v1.0)

| ชั้น | Technology | เหตุผล |
|------|------------|--------|
| Backend | **Django 6 + Python 3.13** | rapid · solid ORM · admin มาให้ |
| Frontend | **Tailwind + htmx + Alpine.js** | server-rendered + interactivity เล็ก ๆ |
| Templating | **Django Templates** | native · เร็ว · no build step |
| Database | **PostgreSQL 17** | jsonb · full-text search · robust |
| PDF | **WeasyPrint** | render html → PDF · ฝังฟอนต์ |
| Cache | **Redis** | session + Django cache · separate `CACHE_REDIS_URL` |
| Queue + scheduler | **django-q2** (Redis-backed) | `@task` shim + `.enqueue()` · `qcluster` worker · DB-backed Schedule rows (no cron) · separate `Q_REDIS_URL` so cache flushes ไม่ nuke queue |
| LINE | **line-bot-sdk-python (v3 webhooks)** | official SDK |
| AI | **Anthropic Claude (Sonnet 4)** | catalog match · reply suggest · summary · quotation draft |
| Storage | **Cloudflare R2** (S3-compatible) | toggle ผ่าน `USE_R2` env · django-storages backend · presigned URLs |
| Search | **Postgres `icontains`** เริ่ม → FTS / Meilisearch ถ้าจำเป็น | |
| TLS proxy (prod) | **Caddy** + on-demand TLS via `/_caddy/ask` | DNS (CNAME) → app · ACME / Let's Encrypt · same shape ใน dev (`tls internal`) |
| Deployment | **VPS + systemd + gunicorn==23 + Nginx (หรือ Caddy)** | `VPS_DEPLOYMENT.md` + `deploy.sh` |
| Monitoring | **Sentry + Plausible** (planned) | error + product analytics |
| CI/CD | **GitHub Actions** (planned) | test + deploy |
| Package | **uv** | เร็วกว่า pip 10 เท่า |

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

## 09 · Communication channels (multi-channel delivery)

ใบเสนอราคา (และข้อความอื่น) ส่งผ่าน **3 channel** · ใช้ร่วมกันได้ในการส่งครั้งเดียว · เซลส์เลือกใน send dialog · default จาก context (ลูกค้ามาจาก LINE → check LINE default · มาจากเว็บ → check email default)

### Channel 1 · LINE Messaging API

**Webhook ที่รับ**
- `message` (text / image / sticker / file) → สร้าง Message + ผูก Conversation
- `follow` → ลูกค้า add LINE OA · สร้าง Customer หรือ link กับที่มีอยู่
- `unfollow` → mark Customer inactive
- `postback` → user กดปุ่มใน Flex Message

**ที่ส่งออก**
- Push message ผ่าน `/v2/bot/message/push` (text / flex)
- Multicast สำหรับ campaign
- Rich menu (optional)

**Rate limits + Security**
- 1,000 messages/sec per channel
- HMAC-SHA256 verify signature ทุก webhook
- Token rotation ทุก 30 วัน
- ไม่ log raw message content (เก็บแค่ ID + metadata)

### Channel 2 · Email

**Provider:** SendGrid (Phase 1) · fallback SMTP ของ tenant ได้ (Pro+ tier)
- จาก `quote@{tenant-slug}.salesdee.app` หรือ custom domain (Pro+)
- subject: `ใบเสนอราคา QT-2026-0142 · บริษัทวัน.ดี.ดี.บิสซิเนส จำกัด`
- HTML body: greeting · summary · CTA "ดูใบเสนอเต็ม" · sales signature
- attachment: PDF (รูปแบบเดียวกับใน `specs/quotation.html`)
- link tracking via redirect URL → log click + open

**Bounce + complaint handling**
- soft bounce → retry 3 ครั้งใน 24 ชม
- hard bounce → mark email invalid · แจ้งเซลส์
- spam complaint → block ทันที

### Channel 3 · SMS

**Provider:** เริ่มที่ Thai SMS gateway (THSMS, ThaiBulkSMS) · option Twilio สำหรับ international
- ข้อความสั้น 70 char Thai หรือ 160 ASCII
- รูปแบบ: `ใบเสนอราคา QT-2026-0142 จากวัน.ดี.ดี. ดูที่ salesdee.app/q/abc · ฟรี`
- ใช้ short link domain (`s.salesdee.app/q/abc`) เพื่อจำกัด char
- ส่งครั้งเดียวต่อใบเสนอ · ตามตอน reminder + ใกล้หมดอายุ

**ข้อจำกัด**
- ไม่ส่ง SMS โดยไม่มีเบอร์ที่ verify แล้ว
- ค่าใช้จ่าย ~0.50 บาท/SMS — ขึ้นกับ tier · Free tier ไม่มี SMS · Starter จำกัด 100/เดือน

### Send dialog · UX

เมื่อเซลส์กด "ส่งใบเสนอ" → modal เปิด:
- ☑ **Email** [คุณนริศ@abc.co.th] — PDF + ลิงก์ดูออนไลน์
- ☑ **LINE** [คุณนริศ · @abc123] — Flex Message พร้อมปุ่ม
- ☐ **SMS** [+66 81 xxx xxxx] — text + short link (ค่าเฉลี่ย ฿0.50)
- ช่องไหนไม่มี contact → grey out + ลิงก์ "เพิ่มเบอร์/อีเมล/LINE"
- custom message field — ข้อความเปิด (เช่น "พี่นริศ · ส่งใบเสนอตามที่คุยกันค่ะ")
- preview ของแต่ละ channel (toggle ดู)
- ปุ่ม "ส่ง 2 channel" → ส่งทั้งหมดที่ check

### Delivery tracking

ทุกการส่งสร้าง `DeliveryLog` entry · เห็นได้ใน Quote detail:
- ✓ Email · ส่ง 10:42 · เปิด 10:48 · คลิกลิงก์ 10:49
- ✓ LINE · ส่ง 10:42 · เปิด 10:45 · คลิกปุ่ม
- — SMS · ไม่ได้ส่ง (เลือกไม่เลือก)
- หาก channel ใด fail → retry หรือ alert เซลส์

---

## 10 · AI (ตัวเสริม · ลดบทบาทจาก v1.0)

### ใช้ที่ไหน (เรียงตามสำคัญ)

**Tier 1 · Onboarding helpers** (ทำให้ catalog ขึ้นเร็ว)
1. **Parse PDF spec sheet** → product fields (vision API)
2. **Parse URL จากเว็บผู้ผลิต** → product fields
3. **Guess column mapping** ใน Excel import (จาก header name)
4. **Suggest category** จากรูปสินค้า

**Tier 2 · Sales helpers** (ช่วยเซลส์ตอบ LINE เร็วขึ้น)
5. **Match products** จากข้อความใน LINE → เสนอ 3 รายการ
6. **Suggest reply** สำหรับ LINE chat (3 ทางเลือก)
7. **Summarize customer** จาก history → 2-3 ประโยค

**Tier 3 · Manager helpers** (ภาพรวม)
8. **Suggest next step** สำหรับดีลที่ค้าง
9. **Flag** ใบเสนอใกล้หมดอายุ
10. **Suggest pricing** จากค่าเฉลี่ยในหมวด

### Model
- **Claude Sonnet 4** สำหรับ matching · summarization · parsing
- **Claude Haiku** สำหรับ task เล็ก ๆ (column guess · category suggest)
- ใน Phase 1: ใช้ Anthropic API ตรง · ไม่ทำ local model

### UX rules
- AI ใช้ **สีเซจ** เสมอ (ตามแบรนด์)
- AI ใส่เครื่องหมาย **✱** หรือ **"D"** avatar กำกับ
- AI เสนอ · ไม่บังคับ · เซลส์ตัดสินสุดท้ายทุกครั้ง
- แสดงเหตุผล ("เพราะลูกค้าเปิดดู 4 ครั้ง") เมื่อเป็นไปได้
- เก็บ feedback (thumbs up/down) เพื่อปรับ prompt
- ห้าม AI กระทำเงียบ (ส่งใบเสนอเอง · ยอมรับเอง · ฯลฯ)

### Cost guardrails
- Rate limit ต่อ tenant ต่อนาที · ต่อวัน
- Cache result ที่ตอบซ้ำได้ (summary refresh ทุก 24 ชม)
- Tier กำหนด token budget ต่อเดือน
- Fallback gracefully เมื่อ AI ล่ม (workflow ยังทำงานได้ · แค่ไม่มี suggestion)

---

## 11 · Multi-tenant

### Shared schema strategy
- 1 database · ทุก tenant-scoped table มี `tenant_id` FK
- `CurrentTenantMiddleware` resolve tenant จาก host (verified TenantDomain → `<slug>.<APP_DOMAIN>` → user membership → `DEV_DEFAULT_TENANT_SLUG`) + activate ผ่าน context var
- `TenantManager` (default `Model.objects`) กรอง `tenant_id` อัตโนมัติ · **fail closed**: no tenant active → return empty + save raises
- `Model.all_tenants` ใช้ใน migrations · platform admin · background tasks ที่ activate tenant เอง
- **RLS (Postgres)** = defense in depth · `enable_tenant_rls("tablename")` ใน RLS migration · `RLS_ENABLED=true` ใน prod ตอน app role ไม่ใช่ owner

### Host routing
- `wandeedee.salesdee.app` → built-in subdomain · resolves from `<slug>.<APP_DOMAIN>`
- `wandeedee.com` (custom domain · tier Pro+) → `TenantDomain(verified=True)` · auto-mint TLS cert via Caddy on-demand
- `salesdee.app` หรือ `app.salesdee.app` → marketing site / login (no tenant)
- `api.salesdee.app` → API (Phase 2)

### On-demand TLS (Caddy)
- Production-shape flow: Caddy `on_demand_tls { ask http://localhost:8000/_caddy/ask }` + catch-all site `https:// { tls cert@email { on_demand } }`
- Django `/_caddy/ask?domain=X` → 200 ถ้า X คือ platform host / built-in subdomain ของ active tenant / verified TenantDomain row · 404 อย่างอื่น (กัน drive-by cert issuance)
- Dev: same flow แต่ `tls internal` (Caddy's own CA · trust ด้วย `sudo caddy trust`) + mkcert wildcard cert สำหรับ `*.salesdee.local`
- Prod: ACME / Let's Encrypt · `tls cert@example.com { on_demand }`

### Feature gating (สามชั้น · first wins)
1. **`settings.PLATFORM_DISABLED_MODULES`** (env-level kill switch) — list of module codes ที่ผู้ดูแล salesdee.com ปิดทั้งระบบ · ใช้ตอน incident หรือ maintenance
2. **`TenantFeatureOverride`** (per-tenant · platform admin manages via Django admin `/admin/tenants/tenantfeatureoverride/`) — FORCE_ON สำหรับ anchor grant / beta · FORCE_OFF สำหรับ dispute · `expires_at` กำหนดได้
3. **`Plan.features`** (default) — `billing_module` · `white_label_pdf` · `custom_domain` · `api_access` · `e_tax_invoice` · `priority_support` · `sla`

Single helper `apps.tenants.features.feature_enabled(tenant, code) → bool` ใช้ทุกที่ที่ต้อง gate (middleware · context processor · `/settings/modules/`).

### Usage quotas
- ต่อ tenant ต่อเดือน (`Usage` model · period = YYYYMM Asia/Bangkok)
- 3 kinds: `line_msgs` · `ai_drafts` · `tax_invoices`
- เพดานอ่านจาก `Plan.limits` · `-1` = unlimited
- `gated(tenant, kind)` context-manager — check ก่อน · increment เฉพาะ body สำเร็จ · skip increment ถ้า exception
- Soft warn ที่ ≥80% (banner ผ่าน context processor) · hard-block เฉพาะ `tax_invoices` (raise `QuotaExceeded` ที่ service layer · 402 ที่ view layer)
- Fail open: increment error ถูก swallow + log — quota glitch ห้าม 500 webhook หรือ AI draft

### Security
- Tenant-isolation test ต่อ tenant-scoped model: data ใน A ไม่เห็นจาก B context
- Audit log (`apps.audit.AuditEvent`) ทุก state change ที่สำคัญ: doc submit / approve / send / tax_invoice issue / payment record / plan change / member role change
- Per-tenant LINE channel (DB-stored token, encrypted) · **per-tenant Anthropic API key** — ⏳ ยังไม่ build · ปัจจุบันใช้ env-level `ANTHROPIC_API_KEY` ร่วมกันทุก tenant + budget cap ผ่าน `ai_drafts` quota
- 2FA TOTP per-user opt-in (`apps.accounts.TwoFactorDevice`)

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

### ⏳ Pending — Path A (customer self-service) — biggest gap
1. **Quote drawer on tenant website** — เพิ่มสินค้าลงตะกร้า "ขอใบเสนอ" (per `specs/furniture-site.html`)
2. **Multi-step quote request form** — contact info → project info → submit
3. **`SalesDocument.source` field** — `"website" / "line" / "manual"` + status `"request"` (เริ่มที่ request เมื่อมาจากเว็บ)
4. **Quote Requests inbox (back-office)** — filter "จาก website" / "จาก LINE" · approve/edit/send

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
- ปล่อย Path A ทีละ piece หรือ build ครบก่อนเปิด anchor?
- Theme system ทำเป็น preset 4 ตัว หรือ tenant pick accent + font?
- Custom domain provisioning UI (วันนี้ผ่าน Django admin) ขึ้นเป็น settings page ตอนไหน?

---

## 15 · ความเสี่ยง

### Technical
- **LINE API rate limit** เมื่อ tenant เยอะ — message queue ตั้งแต่แรก
- **AI cost runaway** — guardrails (rate · cache · tier budget)
- **Multi-tenant data leak** — testing เข้มข้น · audit log
- **PDF rendering slow** — async ผ่าน Celery · cache PDF ที่ render แล้ว
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

## 16 · ทีม

### ระยะ Phase 1 (6 เดือนแรก)
- **Founder / PM** — strategy · sales · customer success
- **Engineer 1** (Django + Python full-stack) — เริ่ม MVP
- **Engineer 2** (frontend + integration) — entry month 3
- **Designer** (part-time / contract) — UI/UX consultation
- **(optional) Designer 2** — เน้น tenant website themes + brand customization

### ระยะ Phase 1.5
- เพิ่ม **Engineer 3** เน้น LINE + AI integration
- **Customer success** part-time

### ระยะ Phase 2
- **Sales** เต็มเวลา
- **Marketing + content** (case study · บล็อก SEO)

---

## 17 · Open questions

1. **Custom domain** — Cloudflare for SSL + DNS · หรือใช้ ACM ของ AWS · ตัดสินที่ deploy
2. **Stripe vs Omise** — เริ่ม Stripe + bank transfer fallback · ใส่ Omise เมื่อมีลูกค้าขอ
3. **Custom Thai font** — commission ปีหน้าถ้าแบรนด์โต
4. **iOS native app** — เริ่มคิดเดือน 9-12 ถ้า PWA limit หนัก
5. **API public** — Phase 2 · OAuth + Webhook
6. **Marketplace template / theme** — Phase 2 · ใครจะ moderate?
7. **PDPA · data residency ไทย** — ใช้ VPS ไทย หรือ Singapore? ตัดสินเมื่อ deploy

---

## 18 · ลิงก์อ้างอิง · design files

ทุกไฟล์อยู่ใน design output:

| ไฟล์ | คอนเทนต์ | ใช้สำหรับ |
|------|----------|----------|
| `specs/design-deck.html` | 24 frames หน้าจอ back-office | UI/UX อ้างอิงสำหรับ inbox · deal · catalog · settings · dashboard |
| `specs/brand-guide.html` | wordmark · palette · typography · voice · usage rules | base CSS tokens · design tokens · brand consistency |
| `specs/furniture-site.html` | tenant public website + 4 themes + customer quote builder | dev สร้าง tenant-facing site (Path A entry · ⏳ ยังไม่ build) |
| `specs/quotation.html` | delivery templates: PDF + Email + LINE Flex + SMS | WeasyPrint template + email body + LINE API payload + SMS spec |
| `specs/website.html` | public marketing site (`salesdee.com`) | reference สำหรับ marketing/landing |
| `specs/prd.md` | เอกสารนี้ | source of truth สำหรับการตัดสินใจ |

### Launch readiness · Phase 1 design coverage
✓ Brand `salesdee.com` applied across ทุกไฟล์
✓ Path A customer flow ครบ (browse → request → review → send → view → accept)
✓ Path B sales flow มี design references ใน deck + delivery templates
✓ Multi-channel delivery (PDF + Email + LINE + SMS) ออกแบบเสร็จ + spec dev ใช้ได้
✓ Catalog onboarding 5 paths ครบ
✓ Tenant theme system 4 แบบ
✓ Public quote view tenant-branded + accept flow

### ที่ขาดในชุดออกแบบ (สำหรับ dev ทำต่อ · ไม่ block launch)
- หน้า **Settings sub-pages** (team · integrations · billing · security) — dev ใช้ pattern จาก settings ใน design deck (frame s2)
- **Mobile views** บางส่วน · เช่น login mobile, deal detail mobile — dev ใช้ pattern จาก mobile frames ที่มีอยู่ (frame mobile + m-extras)
- **Tax invoice + receipt templates** — Phase 1.5 · ไม่ block launch
- **PDF caching ใน S3** — implementation detail · spec ใน Section 09

### ที่ขาดในชุดออกแบบปัจจุบัน (สำหรับ dev ทำต่อ · ไม่ block · ใช้ pattern ที่มี)
- **Quote requests inbox** ใน back-office (ใหม่ใน v2.0) — dev ใช้ inbox + deal detail เป็นต้นแบบ · มี filter "จาก website" / "จาก LINE"
- **Customer quote builder บนเว็บ** — multi-step form · dev ใช้ pattern จาก quote builder ใน back-office (frame q2) + form design จาก deck (auth/onboarding)
- **Product detail page** บน tenant website — dev ใช้ pattern catalog + brand guide
- **Public quote view (customer view of quote)** — frame cf1 ในด deck เป็นต้นแบบ · เพิ่มปุ่ม "ยอมรับ" + signature

---

**บันทึก:** เอกสารนี้ live document · v2.0 เป็นรุ่นล่าสุด · เปลี่ยนเมื่อมีการตัดสินใจใหม่ · เก็บใน git ของทีม · major decision บันทึก commit message ที่ชัด

**Changelog:**
- **v2.2** (14 พ.ค. 2569 · ค่ำ) — PRD sync กับ code · §12 pricing = **Free + 4 paid tier** (Free / Starter 690 / Growth ⭐ 1,890 / Pro 3,890 / Business 9,900) — เอา Trial 30d ออก ใช้ Free forever แทน · §11 เพิ่ม Feature override · Platform kill switch · Caddy on-demand TLS · §07 stack แทน Celery ด้วย django-q2 · §08 เพิ่ม `Plan` · `Usage` · `TenantFeatureOverride` · §04 + §14 annotate สถานะ built ✓ vs pending ⏳ · ระบุชัดว่า Path A + multi-channel + theme system **ยังไม่ build**
- **v2.1.1** (14 พ.ค. 2569 · เย็น) — Launch-ready iteration · brand renamed to `salesdee.com` (38+ wordmarks updated) · marketing site copy updated to v2.1 framing (2 paths · AI as helper) · email + SMS templates added to delivery doc
- **v2.1** (14 พ.ค. 2569 · บ่าย) — confirm Path 1 (sales review เสมอ) · เพิ่ม multi-channel delivery (email + LINE + SMS) · เพิ่ม `DeliveryLog` entity · Section 09 ขยายเป็น "Communication channels"
- **v2.0** (14 พ.ค. 2569 · เช้า) — เพิ่ม Path A website self-service · ลด AI เป็นตัวเสริม · เลื่อน onboarding ขึ้นเป็น Tier 0 · เพิ่ม `Quote.source` field + status workflow ใหม่ · ปรับ roadmap
- **v1.0** (12 พ.ค. 2569) — รุ่นแรก

*salesdee.com PRD v2.2 · 14 พฤษภาคม 2569 · sync กับ code state · ใช้ภายในทีม*
