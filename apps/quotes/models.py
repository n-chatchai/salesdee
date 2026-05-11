"""Quotations (and, later, the rest of the sales-document chain).  Spec: REQUIREMENTS.md §4.7–§4.8.

To build (phase 1 — quotation only):
  - SalesDocument (start with docType=QUOTATION): docNo + revision, customer/contact, dealId,
    issue/valid-until dates, currency, priceMode (EXCL/INCL), status, end-of-bill discount,
    paymentSchedule, terms/notes, bank account, dimension, template, etc.
  - SalesDocLine: groupLabel (ห้อง/โซน), type (ITEM/HEADING/NOTE/DISCOUNT/SHIPPING/INSTALLATION),
    product/variant, description, dims (W/D/H), material/color, images, options, qty, unit,
    unit price, line discount, taxType, withholding rate, amount, cost? (margin)
  - Totals computation (subtotal → end discount → VAT bases per rate → VAT → grand total),
    withholding estimate, BahtText (apps.core.utils.baht_text), rounding
  - Revisions (snapshot history + diff), discount-approval workflow, statuses
  - PDF (WeasyPrint, embedded Thai font), send via link / LINE / email, public accept/sign view
  - Document numbering: generate inside a DB transaction with select_for_update on the sequence row
    (see CLAUDE.md §4.3)

Phase 2 adds the other docTypes (SALES_ORDER, DELIVERY_NOTE, INVOICE, TAX_INVOICE, RECEIPT,
CREDIT_NOTE, DEBIT_NOTE, DEPOSIT) and DocumentLink; consider whether to model them as one
SalesDocument table with a docType field or split per type — decide when building phase 2.

Tenant-owned → inherit ``apps.core.models.TenantScopedModel``.
"""

from apps.core.models import TenantScopedModel  # noqa: F401
