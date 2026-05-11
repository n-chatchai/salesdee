"""PHASE 2 — billing & accounts receivable.  Spec: REQUIREMENTS.md §4.13–§4.14.1.

Scope: invoices / billing notes, full-form tax invoices, receipts, credit & debit notes,
deposit invoices, retention; payment recording + allocation to invoices; withholding-tax-deducted
tracking; AR aging; customer statements; cheques; sales-tax report + ภ.พ.30 summary.

Invariants (CLAUDE.md §4): issued tax documents are immutable; tax-document numbers are gap-free;
rates are snapshotted onto the document.

Empty for now — do not build until phase 1 (CRM + quotation) is shipped.
"""

from apps.core.models import TenantScopedModel  # noqa: F401
