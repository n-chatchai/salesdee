# salesdee. Development Status

**Last Updated:** 13 พฤษภาคม 2569

---

## Feature Status Overview

| Area | Source | Phase | Design | Dev | Unit & Integration | E2E |
|------|--------|-------|--------|-----|---------------------|-----|
| **Multi-tenant isolation (RLS)** | REQ: FR-1.2 | 1 | ✅ | ✅ | ✅ `test_tenant_isolation.py` | ⚠️ 16 tests |
| **User auth (login, signup, password)** | REQ: FR-15.1 | 1 | ✅ | ✅ | ✅ `test_auth_flows.py` | ⚠️ 16 tests |
| **Tenant onboarding (5 steps)** | REQ: FR-1.1 | 1 | ✅ | ✅ | ✅ `test_onboarding.py` | ⚠️ 16 tests |
| **Company settings (tax ID, branch)** | REQ: FR-1.3 | 1 | ✅ | ✅ | ⚠️ Basic | ⚠️ 16 tests |
| **Customer & Contact CRUD** | REQ: FR-4.1-4.2 | 1 | ✅ | ✅ | ✅ `test_deal_hint_customer360.py` | ⚠️ 16 tests |
| **Lead capture (web form)** | REQ: FR-2.1 | 1 | ✅ | ✅ | ✅ `test_leads.py` | ⚠️ 16 tests |
| **LINE OA webhook** | REQ: FR-2.2, FR-16.1; Design: I2 | 1 | ✅ | ✅ | ✅ `test_line.py` | ⚠️ 16 tests |
| **LINE send message/Flex** | REQ: FR-8.3; Design: I2 | 1 | ✅ | ⚠️ | ⚠️ Basic | ⚠️ 16 tests |
| **Kanban pipeline (drag-drop)** | REQ: FR-3.1; Design: D1 | 1 | ✅ | ✅ | ✅ `test_crm_round2.py` | ⚠️ 16 tests |
| **Deal CRUD & activity timeline** | REQ: FR-3.2-3.3 | 1 | ✅ | ✅ | ✅ `test_views.py` | ⚠️ 16 tests |
| **Customer 360 view** | REQ: FR-4.3 | 1 | ✅ | ⚠️ | ⚠️ Basic | ⚠️ 16 tests |
| **Task management** | REQ: FR-5.1-5.2 | 1 | ✅ | ⚠️ | ⚠️ Basic | ⚠️ 16 tests |
| **Catalog (categories, products)** | REQ: FR-6.1-6.2 | 1 | ✅ | ✅ | ✅ `test_catalog.py` | ⚠️ 16 tests |
| **Product variants & options** | REQ: FR-6.4, FR-6.6 | 1 | ✅ | ⚠️ | ✅ `test_catalog.py` | ⚠️ 16 tests |
| **Bundle items** | REQ: FR-6.5 | 1 | ✅ | ⚠️ | ❌ | ⚠️ 16 tests |
| **Quote builder** | REQ: FR-7; Design: Q2 | 1 | ✅ | ✅ | ✅ `test_quotes.py` | ⚠️ 16 tests |
| **Room/zone grouping** | REQ: FR-7.5; Design: Q2 | 1 | ✅ | ✅ | ⚠️ Basic | ⚠️ 16 tests |
| **Quote calculations (VAT, discount)** | REQ: FR-7.11 | 1 | ✅ | ✅ | ✅ `test_quotes.py` | ⚠️ 16 tests |
| **BahtText conversion** | REQ: FR-7.13 | 1 | ✅ | ⚠️ | ✅ `test_bahttext.py` | ⚠️ 16 tests |
| **Auto document numbering** | REQ: FR-7.1 | 1 | ✅ | ✅ | ⚠️ Basic | ⚠️ 16 tests |
| **Quote revisions** | REQ: FR-7.20 | 1 | ✅ | ✅ | ⚠️ Basic | ❌ |
| **PDF generation (Thai font)** | REQ: FR-8.1 | 1 | ✅ | ✅ | ❌ | ❌ |
| **Public quote page (accept/reject)** | REQ: FR-8.4; Design: CF1 | 1 | ✅ | ✅ | ⚠️ `test_quote_from_chat.py` | ❌ |
| **Dashboard KPIs** | REQ: FR-9.1; Design: D1 | 1 | ✅ | ⚠️ | ⚠️ `test_dashboard.py` | ❌ |
| **AI reply suggestions** | REQ: FR-16.1; Design: I2 (AI panel) | 1 | ✅ | ⚠️ | ✅ `test_ai.py`, `test_ai_quotation.py` | ❌ |
| **AI product matching** | REQ: FR-2.1; Design: AI-2 | 1 | ✅ | ⚠️ | ⚠️ Basic | ❌ |
| **Role-based permissions** | REQ: FR-15.2-15.3 | 1 | ✅ | ⚠️ | ✅ `test_permissions.py` | ❌ |
| **Email inbound (forward-in)** | REQ: FR-2.3 | 1 | ✅ | ❌ | ❌ | ❌ |
| **Calendar view** | REQ: FR-5.3 | 1 | ❌ | ❌ | ❌ | ❌ |
| **Automatic follow-up** | REQ: FR-8.6 | 1 | ✅ | ❌ | ❌ | ❌ |
| **Approval workflow** | REQ: FR-7.21 | 1 | ❌ | ❌ | ❌ | ❌ |
| **Margin/cost calculation** | REQ: FR-10.1-10.2 | 1 | ✅ | ❌ | ❌ | ❌ |
| **Sales targets & forecasting** | REQ: FR-9.5 | 1 | ❌ | ❌ | ❌ | ❌ |
| **Reports (win rate, lost analysis)** | REQ: FR-9.3-9.4 | 1 | ❌ | ❌ | ❌ | ❌ |
| **Audit logging** | REQ: FR-15.5 | 1 | ✅ | ❌ | ❌ | ❌ |
| **Sales Order** | REQ: FR-11.1 | 1.5 | ✅ | ❌ | ❌ | ❌ |
| **Delivery tracking** | REQ: FR-11.3-11.5 | 1.5 | ✅ | ❌ | ❌ | ❌ |
| **Tax Invoice / Receipt** | REQ: FR-13.1 | 1.5 | ✅ | ❌ | ❌ | ❌ |
| **AR Aging** | REQ: FR-13.5 | 1.5 | ✅ | ❌ | ❌ | ❌ |
| **Warranty & claims** | REQ: FR-12.1-12.3 | 1.5 | ✅ | ❌ | ❌ | ❌ |
| **Accounting (Journal, Ledger)** | REQ: FR-14.3-14.5 | 2 | ✅ | ❌ | ❌ | ❌ |
| **e-Tax Invoice** | REQ: FR-14.6 | 2 | ✅ | ❌ | ❌ | ❌ |
| **REST API** | REQ: FR-16.3 | 2 | ✅ | ❌ | ❌ | ❌ |

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Features (Phase 1)** | 34 |
| **Features Done** | 18 (53%) |
| **Features Partial** | 9 (26%) |
| **Features Missing** | 7 (21%) |
| **Design Complete** | ✅ All MVP screens |
| **Total Unit & Integration Tests** | 215 |
| **Total E2E Tests** | ~24 (Playwright) |
| **E2E Passing** | ~16 (Chromium) |

### Run Tests

```bash
# Unit & Integration
make test

# E2E (requires server running)
npm run test:e2e
npx playwright test --ui
```