"""Render billing documents (tax invoice / receipt / credit note) to PDF via WeasyPrint.

Same pattern as ``apps.quotes.pdf``: the templates ``@font-face``-load the bundled Sarabun TTFs from
``static/fonts/`` relative to ``base_url`` — no system font or remote fetch. The tax-invoice template
satisfies all Revenue Code §86/4 fields (CLAUDE.md §5.2)."""

from __future__ import annotations

from django.conf import settings
from django.template.loader import render_to_string

from apps.tenants.models import CompanyProfile

from .services import compute_document_totals


def _static_dir() -> str:
    d = settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.BASE_DIR / "static"
    return str(d)


def _render(doc, *, doc_title: str, copy: bool, original_ref: str = "") -> bytes:
    from weasyprint import HTML

    company = CompanyProfile.objects.filter(tenant_id=doc.tenant_id).first()
    html = render_to_string(
        "billing/pdf/document.html",
        {
            "document": doc,
            "totals": compute_document_totals(doc),
            "company": company,
            "doc_title": doc_title,
            "is_copy": copy,
            "original_ref": original_ref,
        },
    )
    return HTML(string=html, base_url=_static_dir()).write_pdf()


def render_tax_invoice_pdf(doc, *, copy: bool = False) -> bytes:
    return _render(doc, doc_title="ใบกำกับภาษี", copy=copy)


def render_receipt_pdf(doc, *, copy: bool = False) -> bytes:
    return _render(doc, doc_title="ใบเสร็จรับเงิน", copy=copy)


def render_credit_note_pdf(doc, *, copy: bool = False) -> bytes:
    ref = doc.references_document.doc_number if doc.references_document_id else ""
    return _render(doc, doc_title="ใบลดหนี้", copy=copy, original_ref=ref or "")
