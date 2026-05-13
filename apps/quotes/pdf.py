"""Render a quotation to PDF via WeasyPrint. The PDF template ``@font-face``-loads the bundled
Sarabun TTFs from ``static/fonts/`` (relative to ``base_url`` below) — no system font or remote
fetch needed. See CLAUDE.md §7."""

from __future__ import annotations

from django.conf import settings
from django.template.loader import render_to_string

from apps.tenants.models import CompanyProfile

from .models import SalesDocument
from .services import compute_document_totals


def render_quotation_pdf(document: SalesDocument) -> bytes:
    from weasyprint import HTML

    company = CompanyProfile.objects.filter(tenant_id=document.tenant_id).first()
    html = render_to_string(
        "quotes/pdf/quotation.html",
        {"document": document, "totals": compute_document_totals(document), "company": company},
    )
    static_dir = settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.BASE_DIR / "static"
    return HTML(string=html, base_url=str(static_dir)).write_pdf()
