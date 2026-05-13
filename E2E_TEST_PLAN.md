# E2E Test Plan — salesdee.

**Last Updated:** 13 พฤษภาคม 2569

---

## Test Framework Recommendation

| Option | Pros | Cons |
|--------|------|------|
| **Playwright** | ✅ Best for Django/htmx, auto-wait, screenshot/video | ❌ ไม่มีใน project |
| **Cypress** | ✅ Popular, good DX | ❌ ไม่มีใน project |
| **Selenium** | ✅ มีอยู่แล้ว (ถ้ามี) | ❌ Legacy, slow |
| **pytest + requests** | ✅ ใช้ existing pytest | ⚠️ ไม่ใช่ real browser |

**แนะนำ:** Playwright — เหมาะกับ Django + htmx และ CI/CD integration

---

## Critical User Flows (E2E Priority)

### P0 — Must Test (Core Revenue Flows)

| # | Flow | Description | Coverage |
|---|------|-------------|----------|
| E2E-01 | **Signup → Onboarding → Create Quote** | User signup → 5-step onboarding → create first quote | Full |
| E2E-02 | **Lead → Deal → Quote → Send** | Lead from web form → create deal → build quote → send via LINE | Full |
| E2E-03 | **Customer Accepts Quote Online** | Customer receives link → views quote → signs & accepts → status updates | Full |
| E2E-04 | **Kanban Stage Change** | Drag deal from one stage to another → verify data update | Full |

### P1 — Should Test (Secondary Flows)

| # | Flow | Description | Coverage |
|---|------|-------------|----------|
| E2E-05 | **LINE Webhook → Lead Created** | Send LINE message → webhook triggers → lead created in CRM | Full |
| E2E-06 | **Quote PDF Download** | Open quote detail → click download → verify PDF content | Partial |
| E2E-07 | **Customer Rejects Quote** | Customer receives link → views quote → clicks reject → status updates | Full |
| E2E-08 | **Create Customer & Contact** | Add new customer → add multiple contacts → verify relations | Full |
| E2E-09 | **Product Selection in Quote** | Open quote builder → search catalog → select product → verify added | Full |

### P2 — Nice to Have

| # | Flow | Description | Coverage |
|---|------|-------------|----------|
| E2E-10 | **Task Creation from Deal** | Open deal → create task → assign → verify in task list | Full |
| E2E-11 | **AI Reply Suggestion** | Open LINE conversation → verify AI suggestion appears | Partial |
| E2E-12 | **Quote Revision** | Send quote → create revision → verify new version | Full |
| E2E-13 | **Multi-tenant Isolation (E2E)** | Login as Tenant A user → verify cannot see Tenant B data | Full |

---

## Test Scenarios by Feature

### 1. Authentication & Onboarding

| Scenario | Steps | Expected Result |
|----------|-------|-----------------|
| Signup new tenant | 1. Open signup page → 2. Fill business name, email, password → 3. Submit | Redirect to onboarding step 1 |
| Onboarding 5 steps | 1. Company info → 2. Industry → 3. Team members → 4. Connect LINE → 5. Import data | Complete → redirect to dashboard |
| Login existing user | 1. Open login → 2. Enter credentials → 3. Submit | Redirect to dashboard |

### 2. Lead & Deal Management

| Scenario | Steps | Expected Result |
|----------|-------|-----------------|
| Web form lead capture | 1. Open `/intake/` → 2. Fill form (name, phone, product) → 3. Submit | Lead created, shown in CRM |
| Kanban drag-drop | 1. Open pipeline → 2. Drag deal from "ลูกค้าใหม่" to "ส่งใบเสนอราคา" | Stage updated, activity logged |
| Create deal from lead | 1. Open lead → 2. Click "สร้างดีล" → 3. Fill deal info → 4. Save | Deal created, linked to lead |

### 3. Quote Builder

| Scenario | Steps | Expected Result |
|----------|-------|-----------------|
| Create quote from catalog | 1. New quote → 2. Select customer → 3. Add products from catalog → 4. Save | Quote created with lines |
| Add room/zone grouping | 1. In quote → 2. Click "เพิ่มกลุ่ม" → 3. Name group → 4. Add items | Room grouping displayed |
| Calculate totals | 1. Add items with qty, price → 2. Add discount → 3. View totals | VAT, discount, total correct |
| Generate PDF | 1. Open quote → 2. Click "ดาวน์โหลด PDF" → 3. Verify content | PDF downloaded with Thai font |

### 4. LINE Integration

| Scenario | Steps | Expected Result |
|----------|-------|-----------------|
| Receive LINE message | 1. Send message to LINE OA → 2. Webhook receives → 3. View in inbox | Message appears in inbox |
| Send quote via LINE | 1. Open quote → 2. Click "ส่ง via LINE" → 3. Select customer → 4. Send | Flex message sent |
| Quote link via LINE | 1. Customer receives LINE → 2. Clicks link → 3. Opens public quote page | Quote page loads |

### 5. Public Quote Page

| Scenario | Steps | Expected Result |
|----------|-------|-----------------|
| View quote without login | 1. Open public quote link → 2. View quote details | Quote displayed, no login needed |
| Accept quote with signature | 1. Open quote → 2. Click "ยอมรับ" → 3. Enter name, signature → 4. Submit | Status = Accepted, timestamp logged |
| Reject quote | 1. Open quote → 2. Click "ปฏิเสธ" → 3. Enter reason → 4. Submit | Status = Rejected |

### 6. Multi-tenancy

| Scenario | Steps | Expected Result |
|----------|-------|-----------------|
| Tenant A cannot see B | 1. Login as Tenant A → 2. Try to access Tenant B data | 403 or empty result |
| User with multiple tenants | 1. Login with user in 2 tenants → 2. Switch tenant | Data switches correctly |

---

## Browser & Environment Matrix

| Browser | Environment | Resolution |
|---------|-------------|------------|
| Chrome | Desktop (1200×800) | ✅ Primary |
| Chrome | Mobile (390×844) | ✅ Responsive test |
| Firefox | Desktop | ⚠️ If needed |
| Safari | Desktop | ⚠️ If needed |

---

## Test Data Requirements

| Data Type | Setup Required | Notes |
|-----------|----------------|-------|
| Tenant | 2 tenants (Tenant A, Tenant B) | For isolation tests |
| Users | Owner, Admin, Sales per tenant | Role-based tests |
| Customers | 3-5 customers per tenant | Various stages |
| Products | 10-20 products with variants | Catalog tests |
| Quotes | 2-3 quotes in various states | Quote flow tests |

---

## CI/CD Integration

```yaml
# .github/workflows/e2e.yml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm install
      - run: npx playwright install --with-deps
      - run: npx playwright test
        env:
          BASE_URL: ${{ secrets.BASE_URL }}
          LINE_WEBHOOK_SECRET: ${{ secrets.LINE_WEBHOOK_SECRET }}
```

---

## Test Execution

```bash
# Install Playwright
npm install -D @playwright/test
npx playwright install --with-deps

# Run all E2E tests
npx playwright test

# Run specific flow
npx playwright test tests/quote-flow.spec.ts

# Run with UI (debug)
npx playwright test --ui

# Run on specific browser
npx playwright test --project=chromium
```

---

## Coverage Target

| Phase | Target E2E Tests |
|-------|------------------|
| MVP (Phase 1) | 25-30 tests |
| Current | 0 tests |
| Gap | **25-30 tests needed** |

---

## Next Steps

1. **Install Playwright** — `npm install -D @playwright/test`
2. **Create test files** — `tests/e2e/`
3. **Setup fixtures** — Create test data script
4. **Write P0 flows first** — Core revenue flows
5. **Run in CI** — GitHub Actions

ต้องการให้เริ่มเขียน E2E tests เลยไหมครับ?