# salesdee. · เอกสารแผนสินค้า

**รุ่น 1.0 · 12 พฤษภาคม 2569 · สำหรับ developer + designer + go-to-market**

> เอกสารนี้สรุปการตัดสินใจที่ทีมได้ตกลงร่วมกัน ใช้เป็นแหล่งอ้างอิงเดียวกันก่อนเริ่มสร้างจริง · เมื่อใดที่มีคำถาม "ทำไมเลือกแบบนี้" ให้กลับมาดูที่นี่

---

## 01 · วิสัยทัศน์และตำแหน่งของแบรนด์

### หนึ่งบรรทัด
**salesdee.** เปลี่ยน LINE chat ของ SME ไทยให้เป็นใบเสนอราคาภายใน 30 วินาที

### ปัญหาที่แก้
SME ไทย 90% รับลูกค้าผ่าน LINE Official Account · เซลส์ใช้เวลา 20-40 นาทีต่อใบเสนอ (ตรวจ catalog, พิมพ์ใน Excel, ส่งกลับ LINE) · ใบเสนอที่ได้ไม่สม่ำเสมอ ตรากระดาษหาย ไม่รู้ว่าลูกค้าเปิดดูหรือเปล่า ดีลตกหายระหว่างทาง

### วิธีแก้ของเรา
- รับ LINE chat ของลูกค้าเข้าระบบ
- ผู้ช่วยจับคู่ข้อความกับสินค้าจาก catalog
- เซลส์ตรวจและกดส่งภายในไม่กี่นาที
- ระบบส่งใบเสนอกลับเข้า LINE chat ทันที (PDF + Flex Message)
- ติดตามได้ว่าลูกค้าเปิดดูเมื่อใด กี่ครั้ง
- เก็บประวัติทุกอย่างใน CRM ที่ search ได้

### ตำแหน่งในตลาด
ไม่ใช่ generic CRM (HubSpot, Salesforce) — ใหญ่เกินไป  
ไม่ใช่ chat-only (LINE OA Manager) — ตื้นเกินไป  
**คือ CRM ที่เริ่มจาก LINE conversation และรู้จัก vertical** (เริ่มที่เฟอร์นิเจอร์สำนักงาน)

---

## 02 · ลูกค้าหลักและ Persona

### ลูกค้าแรก (anchor customer)
**บริษัท วัน.ดี.ดี.บิสซิเนส จำกัด**
- ขายเฟอร์นิเจอร์สำนักงาน B2B
- ทีมงาน 8 คน (เซลส์ 3 · admin 2 · ช่าง 3)
- 60% ของ lead มาจาก LINE
- รายได้ปัจจุบัน 20-30M บาท/ปี
- เป้าหมายเข้าใช้ salesdee. **ก่อนสิ้น Q3/2569**

### Persona 1 · เซลส์ (พี่มะลิ)
- หญิง 32 ปี · 8 ปีในวงการ
- ทำงาน 9-18 น. + ตอบ LINE จนถึง 22 น.
- ใช้มือถือมากกว่าเดสก์ท็อป 70%
- จำลูกค้ารายตัวได้ แต่ไม่มีระบบสำรอง
- **pain ใหญ่สุด:** พิมพ์ใบเสนอใน Excel ซ้ำ ๆ + จำราคาไม่ได้ ต้องเปิด catalog ทุกครั้ง
- **ความสำเร็จ:** ปิดดีลใหญ่ ๆ ได้สม่ำเสมอ ลูกค้าจำชื่อได้

### Persona 2 · เจ้าของ (พี่สมชาย)
- ชาย 48 ปี · ก่อตั้งบริษัทมา 12 ปี
- ใช้ Excel จด deal ส่วนตัว · ดูภาพรวมยอดขายไม่ออก
- ใช้มือถือเช็ค LINE และเปิดดูยอด · ใช้คอมตอนทำเอกสาร
- **pain ใหญ่สุด:** ไม่รู้ว่าทีมเซลส์มี deal อะไรค้างอยู่บ้าง · ดีลใหญ่หายไปไหน
- **ความสำเร็จ:** เห็นภาพรวมยอดขาย รู้ว่าทีมไหนทำดี ทีมไหนต้องช่วย

### Persona 3 · admin/จัดซื้อ (น้องปลา)
- หญิง 26 ปี · ดูแลสต๊อก จัดส่ง การเงิน
- รับใบเสนอจากเซลส์ ปรับแก้ ออกใบกำกับภาษี ใบเสร็จ
- ใช้คอมเป็นหลัก
- **pain ใหญ่สุด:** ใบเสนอที่เซลส์ส่งมาไม่สม่ำเสมอ · ราคาบางอันผิด · ต้องตามแก้
- **ความสำเร็จ:** เอกสารทั้งหมดถูกต้อง ส่งทันเวลา ระบบบัญชีตรง

---

## 03 · User Journey 5 หลัก

### Journey 1 · จาก LINE → ใบเสนอ (สำคัญที่สุด)
```
ลูกค้าทักใน LINE OA → ระบบรับข้อความเข้า inbox
  ↓
ผู้ช่วยอ่านข้อความ + จับคู่กับ catalog (เสนอ 3 รายการ)
  ↓
เซลส์ตรวจ + ปรับ + กด "สร้างใบเสนอ"
  ↓
ระบบสร้าง PDF + ส่ง LINE Flex กลับเข้า chat
  ↓
ลูกค้าเปิดดู → ระบบ track + แจ้งเซลส์
  ↓
ลูกค้ายอมรับ → ดีลปิด · แจ้ง admin ทำใบกำกับ
```

**เป้าหมาย:** 30 วินาทีจากข้อความเข้า → ใบเสนอส่งกลับได้

### Journey 2 · จัดการดีลที่กำลังเปิด
- ดู Kanban (เสนอราคา · ติดตาม · ต่อรอง · ปิดได้)
- คลิกดีล → เห็นประวัติ LINE chat + ใบเสนอ + activity ล่าสุด
- ผู้ช่วยแนะนำ next step ("ลูกค้าเปิด 4 ครั้ง ลองตามตอนนี้")
- บันทึก call/visit/note ในดีล

### Journey 3 · ทำใบกำกับภาษีและใบเสร็จ (Phase 1.5)
- จากใบเสนอที่ปิดได้ → กด "ทำใบกำกับ"
- ระบบ generate ตามข้อมูลเดิม
- admin ตรวจ → ส่ง email
- เก็บเข้าระบบบัญชีอัตโนมัติ (export CSV)

### Journey 4 · ดูภาพรวม (เจ้าของ)
- หน้าหลัก: รายได้เดือนนี้ vs เดือนก่อน · ดีลที่ต้องตาม · ผู้ช่วยสรุปสิ่งสำคัญ
- รายงาน: funnel · ผลงานเซลส์ · สินค้าขายดี · ลูกค้าซื้อสูงสุด

### Journey 5 · จัดการ catalog (Phase 1)
- import จาก PDF/Excel/URL (ผู้ช่วยช่วย parse)
- ปรับราคา ตั้งสถานะ มองเห็น/ภายใน/ฉบับร่าง
- bulk action สำหรับการปรับเป็นกลุ่ม

---

## 04 · ฟีเจอร์เฟส 1 (MVP สำหรับวัน.ดี.ดี.)

ระยะเวลา: **8-10 สัปดาห์** จากเริ่ม code

### ที่ต้องมี (must-have)
1. **เชื่อมต่อ LINE Official Account** — รับข้อความเข้า inbox
2. **กล่องข้อความรวม** — แสดง chat ทุก thread จากลูกค้าทุกคน
3. **ผู้ช่วย match สินค้า** — อ่านข้อความและเสนอ catalog items
4. **ตัวสร้างใบเสนอ** — สร้างจาก template ที่กำหนด
5. **PDF generator** — render ผ่าน WeasyPrint ส่งเป็นไฟล์
6. **LINE Flex Message** — ส่ง quote summary กลับเข้า LINE chat
7. **CRM พื้นฐาน** — ลูกค้า · ดีล · activities · search
8. **Pipeline Kanban** — 5-7 stage มาตรฐาน
9. **Catalog management** — เพิ่ม/แก้สินค้า · หมวด · ราคา · รูป
10. **Multi-tenant** — แต่ละบริษัทมีข้อมูลแยก แต่ใช้ระบบเดียว

### ที่ไม่มีใน Phase 1
- ใบกำกับภาษี · ใบเสร็จ → Phase 1.5
- รายงานละเอียด → มีแค่ basic metrics ที่หน้าหลัก
- Mobile app (native) → ใช้ PWA แทน
- หลายภาษา → ไทย + อังกฤษพื้นฐาน
- Integration อื่น ๆ (Slack, Email, etc.) → Phase 2

---

## 05 · ฟีเจอร์เฟส 1.5 (3-4 เดือนหลังเปิดตัว)

- **ตัวสร้างใบกำกับภาษี + ใบเสร็จ** — ตามแบบฟอร์มกรมสรรพากร
- **หน้าลูกค้ารับใบเสนอออนไลน์** — กดยอมรับผ่านลิงก์ · เซ็นชื่อ digital
- **รายงานละเอียด** — funnel · revenue trend · sales rep performance
- **Email notifications** — ส่ง summary ทุกเช้า · alert เมื่อลูกค้าเปิดดู
- **Tasks/Reminders** — ตามดีล · นัดประชุม
- **Export ข้อมูล** — CSV สำหรับ admin
- **Public catalog page** — เว็บไซต์สาธารณะของแต่ละ tenant

---

## 06 · ฟีเจอร์เฟส 2 (6 เดือน+)

- **Integration ใหม่** — Slack · Email · Google Sheets
- **Voice หรือ video** — บันทึก call กับลูกค้า
- **AI workflows** — automation รุ่นล้ำ
- **Marketplace** — template หลายรูปแบบ
- **Vertical expansion** — รองรับมากกว่าเฟอร์นิเจอร์ (จราจร อุปกรณ์ทันตกรรม)

---

## 07 · Tech stack

### ทำไมเลือก stack นี้
- **เร็วในการพัฒนา** — Django + htmx ไม่ต้องเขียน frontend แยก
- **เหมาะกับทีมเล็ก** — ใช้คนเขียน Python 1-2 คนก็เริ่มได้
- **Maintenance ง่าย** — server-rendered, debug ง่าย
- **ค่าใช้จ่ายต่ำ** — host บน VPS ได้ ไม่ต้องใช้ K8s
- **เรียนรู้เร็ว** — เปลี่ยนทีมงานในอนาคตได้ง่าย

### Stack เต็ม
| ชั้น | Technology | เหตุผล |
|------|------------|--------|
| Frontend | **Tailwind CSS + htmx + Alpine.js** | Server-rendered พร้อม interactivity เล็ก ๆ ที่จำเป็น |
| Templating | **Django Templates** | Native to Django · เร็ว · ไม่ต้องการ build step |
| Backend | **Django 6 + Python 3.13** | Rapid development · solid ORM · admin มาให้ |
| Database | **PostgreSQL 17** | Robust · jsonb support · full-text search |
| PDF | **WeasyPrint** | render html → PDF ฝังฟอนต์ได้ดี · open source |
| Cache/Queue | **Redis** | session · cache · Celery broker |
| Background tasks | **Celery** | งาน async เช่น LINE webhook · ส่ง email · render PDF |
| LINE | **line-bot-sdk-python** | Official SDK |
| AI | **Claude API หรือ Gemini API** | สำหรับ text understanding + matching |
| Search | **Postgres FTS เริ่มต้น** → Meilisearch ถ้าต้องการเร็วขึ้น | |
| Storage | **S3-compatible** (Cloudflare R2 / Wasabi) | ราคาถูก · รูปสินค้า · PDF เก่า |
| Deployment | **Docker + VPS** เริ่ม → Kubernetes เมื่อ scale | |
| Monitoring | **Sentry + Plausible Analytics** | error + product analytics |
| CI/CD | **GitHub Actions** | test + build + deploy |
| Package manager | **uv** | เร็วกว่า pip มาก |

### ไม่ใช้
- **React/Vue/Svelte SPA** — ไม่จำเป็นและทำให้ทีมต้องดู 2 stack
- **GraphQL** — overkill สำหรับงานนี้ · REST + htmx เพียงพอ
- **NoSQL หลัก** — Postgres ทำหน้าที่ทุกอย่าง
- **Serverless** — เพิ่ม cold start และ debug ยาก

---

## 08 · โครงสร้างฐานข้อมูล (key entities)

```
Tenant (บริษัทที่ใช้ระบบ)
  ├─ name, slug, logo, address, tax_id
  ├─ palette_override (option override สีแบรนด์)
  └─ plan (free / pro / business)

User (พนักงานในแต่ละ tenant)
  ├─ tenant_id, email, name, role (owner/admin/sales/viewer)
  ├─ line_user_id (link กับ LINE personal account)
  └─ avatar, preferences

Customer (ลูกค้าของ tenant)
  ├─ tenant_id, name, contact_name, phone, email
  ├─ company, tax_id, address
  ├─ line_user_id (ลูกค้าใน LINE OA)
  ├─ tags, segment, lifetime_value (computed)
  └─ first_seen, last_active

Conversation (LINE thread)
  ├─ tenant_id, customer_id, line_thread_id
  ├─ status (open/closed/archived)
  └─ assigned_to (user_id)

Message (ในแต่ละ conversation)
  ├─ conversation_id, direction (in/out), type (text/image/sticker)
  ├─ content, line_message_id, ai_parsed (jsonb)
  └─ timestamp

Product (สินค้าใน catalog)
  ├─ tenant_id, sku, name, slug, category_id
  ├─ description, specs (jsonb), images
  ├─ base_price, variants (jsonb), stock_status
  ├─ visibility (public/internal/draft)
  └─ tags, sales_count, last_modified

Category (หมวดสินค้า)
  ├─ tenant_id, name, slug, parent_id (tree)
  ├─ icon, image, sort_order
  └─ description (SEO)

Deal
  ├─ tenant_id, customer_id, name, value
  ├─ stage (lead/qualified/proposal/negotiate/won/lost)
  ├─ owner (user_id), source (line/web/referral/...)
  ├─ probability, expected_close_date
  └─ conversation_ids (linked threads)

Quote (ใบเสนอราคา)
  ├─ tenant_id, deal_id, number (QT-2026-NNNN)
  ├─ customer_snapshot (jsonb · ข้อมูล ณ เวลาออกใบเสนอ)
  ├─ items (jsonb), subtotal, discount, tax, total
  ├─ status (draft/sent/viewed/accepted/expired/rejected)
  ├─ valid_until, sent_at, accepted_at
  └─ public_token (สำหรับ public link · signed)

QuoteEvent (track ทุก activity)
  ├─ quote_id, type (sent/viewed/accepted/rejected)
  ├─ actor (customer/system), timestamp
  └─ metadata (ip, user_agent, page_viewed)

Activity (timeline entries)
  ├─ tenant_id, deal_id, type (call/visit/note/quote_sent/...)
  ├─ user_id (ใครทำ), description
  └─ timestamp, metadata
```

หมายเหตุ — multi-tenant ใช้ `tenant_id` foreign key · ทุก query กรองด้วย middleware · ห้าม raw query โดยไม่กรอง

---

## 09 · LINE integration

### Webhook ที่รับ
- `message` (text/image/sticker/file) → สร้าง Message + Conversation
- `follow` → ลูกค้า add LINE OA · สร้าง Customer ใหม่ (หรือ link)
- `unfollow` → mark Customer inactive
- `postback` → user กดปุ่มใน Flex Message

### ที่ส่งออก
- Push message (text + flex) ผ่าน `/v2/bot/message/push`
- Multicast สำหรับ campaign
- Rich menu (ถ้า tenant configure)

### Rate limits
- 1,000 messages/sec per channel
- 500 messages/month free tier (ของ LINE) · เกินต้องเสียเงิน

### Security
- Verify signature ของทุก webhook (HMAC-SHA256)
- Token rotation ทุก 30 วัน
- ห้าม log raw message content (เก็บแค่ ID + metadata)

---

## 10 · AI (ผู้ช่วยอัจฉริยะ)

### ใช้ที่ไหน
1. **Match สินค้าจากข้อความ** — รับ text → return top 3 products
2. **สรุปประวัติลูกค้า** — รับ messages + deals → summary 2-3 ประโยค
3. **แนะนำ next step** — ตามดีลที่ค้าง · เตือนใบเสนอใกล้หมดอายุ
4. **ร่างข้อความ** — แนะนำ reply ให้เซลส์เลือก 2-3 รูปแบบ
5. **คาดการณ์ความน่าจะปิด** — score จาก signals (เปิดใบเสนอกี่ครั้ง · time since last touch)

### Model ที่ใช้
- เริ่ม: **Claude Sonnet 4** สำหรับ matching + summarization · ราคาดี ผลลัพธ์เสถียร
- Fallback: **Gemini Flash** สำหรับ task เบา ๆ
- Local: คิดถึงในอนาคต ถ้า volume สูง · embedding model สำหรับ semantic search

### Cost guardrails
- ทุก AI request ผ่าน rate limiter (per tenant)
- Cache result ที่ตอบซ้ำได้ (เช่น summary ของลูกค้า — refresh ทุก 24 ชม)
- Tier ของ tenant กำหนด token budget ต่อเดือน

### UX rules
- AI ใช้สีเซจเสมอ (ตามแบรนด์)
- ไม่บังคับ user follow คำแนะนำ · เป็น suggestion เท่านั้น
- แสดงเหตุผล ("เพราะลูกค้าเปิดดู 4 ครั้ง") เมื่อให้คำแนะนำ
- เก็บ feedback (thumbs up/down) เพื่อปรับ prompt

---

## 11 · Multi-tenant strategy

### ทาง shared schema (ที่เลือก)
- 1 database · ทุก table มี `tenant_id`
- Django middleware ระบุ tenant จาก subdomain (`wandeedee.salesdee.app`)
- ทุก ORM query กรองด้วย `TenantManager` อัตโนมัติ
- การ migration ใช้ร่วมกันทั้งหมด

### ทำไมไม่ใช้ทาง separate database
- Operational overhead สูง (backup, migration, upgrade ต่อ tenant)
- เริ่มต้นไม่ต้องการ isolation ระดับนั้น
- ถ้าวันหนึ่งมี enterprise customer ที่ต้อง isolated → migrate เฉพาะรายไปได้

### ความปลอดภัย
- Test ครอบคลุม: ห้าม leak ระหว่าง tenants
- Audit log ทุก query ที่ผ่าน middleware
- ห้าม raw SQL ใน application code (ผ่าน ORM เท่านั้น)

---

## 12 · กลยุทธ์ราคา

### Free tier (สำหรับลองใช้)
- 1 user
- 50 LINE messages/month รับ
- 10 ใบเสนอ/month
- powered-by salesdee. แสดงบนใบเสนอ
- 30 วัน trial เต็มฟีเจอร์

### Starter — 990 บาท/เดือน (target: SME 1-3 คน)
- 3 users
- 1,000 LINE messages/month
- ใบเสนอไม่จำกัด
- ลบ powered-by ได้
- PDF custom logo

### Pro — 2,490 บาท/เดือน (target: SME 5-10 คน · core)
- 10 users
- 5,000 LINE messages/month
- ผู้ช่วย AI เต็มที่
- รายงานละเอียด
- export ข้อมูล
- support email + priority

### Business — 7,990 บาท/เดือน (target: บริษัทกลาง)
- ไม่จำกัด users
- ไม่จำกัด messages (fair use)
- White-label option
- API access
- onboarding 1-1
- SLA + support phone

### กลยุทธ์เริ่มต้น
- wandeedee ใช้ฟรี 6 เดือนแลก feedback + case study
- ลูกค้า 1-10 ใช้ Pro tier ในราคาพิเศษ (50% off ปีแรก)
- ไม่ตั้งราคาเพื่อหวังกำไรในปีแรก — focus retention + word of mouth

---

## 13 · Success metrics

### Phase 1 (เปิดตัวกับ wandeedee)
- **ใช้งานจริงทุกวัน** — เซลส์ทั้ง 3 คน login ทุกวัน
- **เร็วกว่าเดิม** — เวลาทำใบเสนอลดลงจากเฉลี่ย 25 นาที → < 5 นาที
- **ดีลตามได้มากขึ้น** — จำนวนดีลที่ "ตามแบบมีโครงสร้าง" เพิ่มขึ้น 3x
- **ลูกค้าใหม่จากในระบบ** — wandeedee แนะนำ salesdee. ให้คู่ค้าอย่างน้อย 2 ราย

### Phase 1.5 (3-6 เดือนหลังเปิดตัว)
- **10 paying tenants** ใช้งานจริง
- **Net Revenue Retention > 100%** — ลูกค้าอยู่และจ่ายเพิ่ม
- **NPS > 50** จาก paying tenants
- **ผ่าน LINE > 70%** ของใบเสนอที่ออก

### Phase 2 (12 เดือนหลังเปิดตัว)
- **100 paying tenants**
- **MRR 500,000 บาท/เดือน**
- **Vertical 2** เปิดตัว (อุปกรณ์อะไรสักอย่าง — TBD)

---

## 14 · Roadmap (6 เดือนแรก)

| เดือน | งานหลัก | milestone |
|------|---------|-----------|
| 1 | Setup project · auth · multi-tenant · base UI | ทีม login ได้ + เห็น dashboard เปล่า |
| 2 | LINE integration · inbox · catalog management | รับ chat จาก wandeedee LINE OA |
| 3 | ตัวสร้างใบเสนอ · PDF render · LINE Flex output | ออกใบเสนอแรกผ่านระบบ |
| 4 | CRM (deals/customers/timeline) · pipeline · AI matching | wandeedee ใช้ทดสอบทุกวัน · เก็บ bug |
| 5 | Polish · onboarding flow · public homepage · settings | เปิดให้ลูกค้า 1-3 รายแรกลองใช้ |
| 6 | Reports พื้นฐาน · billing (Stripe) · marketing site | เปิด Starter + Pro tier · เริ่มเก็บเงิน |

---

## 15 · ความเสี่ยงที่ต้องระวัง

### Technical
- **LINE API rate limit** — ลูกค้าโตเร็ว · ต้องคิด architecture สำหรับ message queue ตั้งแต่ต้น
- **AI cost runaway** — guardrail ดี · cache · tier-based budget
- **Multi-tenant data leak** — testing เข้มข้น · audit log ทุก query

### Product
- **Vertical fit** — เริ่มที่เฟอร์นิเจอร์อาจไม่กว้างพอ · ต้องคิดถึง vertical 2 ก่อน 6 เดือน
- **AI accuracy** — ผู้ช่วย match สินค้าผิดอาจทำให้ลูกค้าเสีย trust · test ครอบคลุม + เซลส์ตรวจก่อนเสมอ
- **LINE dependency** — ถ้า LINE เปลี่ยน policy หรือเก็บค่า API แพง · มี fallback (email · web form)

### Business
- **Anchor customer dependence** — ถ้า wandeedee เลิกใช้ · ต้องมี case study ก่อนเพื่อไม่เริ่มจากศูนย์ใหม่
- **Competitor (Line OA Manager · HubSpot Thai)** — ของเราต้อง 10x ดีกว่าไม่ใช่แค่ดีกว่านิดเดียว
- **PDPA Thai compliance** — ทำตามตั้งแต่ต้น · มี privacy policy + data export

---

## 16 · ทีม

### ระยะ Phase 1 (6 เดือนแรก)
- **Founder/PM** (เอง) — strategy · sales · customer success
- **Engineer 1** (Django + Python full-stack) — เริ่มที่ MVP
- **Engineer 2** (frontend + design polish) — entry mid-3
- **Designer** (part-time / contract) — UI/UX consultation

### ระยะ Phase 1.5
- เพิ่ม **Engineer 3** เน้น LINE integration + scaling
- **Customer success** part-time

### ระยะ Phase 2
- **Sales** เต็มเวลา (ขยายลูกค้า)
- **Marketing/Content** (ทำ case study + บล็อก SEO)

---

## 17 · ส่วนที่ยังไม่ตัดสินใจ (open questions)

1. **Hosting** — VPS ไทย (ราคา) vs AWS/GCP (latency · scaling) → ตัดสินใจหลังทำ load test
2. **Stripe vs Omise** — ระบบเก็บเงิน · Omise ไทย แต่ Stripe ใช้กว้างกว่า · เริ่มที่ Stripe + ทำ bank transfer fallback
3. **Custom Thai font** — ปีหน้าจะ commission ฟอนต์ของแบรนด์เองไหม
4. **iOS app native** — เมื่อ PWA limit หนัก · เริ่มคิดเดือน 9-12
5. **Open source บางส่วน** — เช่น LINE integration library · ดีต่อ recruitment

---

## 18 · ลิงก์อ้างอิง

- **Design deck**: `salesdee-design-deck.html` (24 หน้าจอ)
- **Brand guide**: `salesdee-brand-guide.html` (wordmark + palette + voice)
- **PDF + LINE templates**: `salesdee-pdf-and-line.html`
- **Anchor customer**: บริษัท วัน.ดี.ดี.บิสซิเนส · LINE Official `@wandeedee`

---

**บันทึก:** เอกสารนี้ live document · ปรับเมื่อมีการตัดสินใจใหม่ · เก็บใน git ของทีม · ทุก major decision บันทึกในส่วน "Decision Log" (ถัดไปจะเพิ่ม)

*salesdee. PRD v1.0 · 12 พฤษภาคม 2569 · ใช้ภายในทีม*
