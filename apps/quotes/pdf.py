"""Render a quotation to PDF via WeasyPrint. The template embeds no remote fonts; the system
needs a Thai-capable font (e.g. ``fonts-thai-tlwg`` on Linux) — or bundle Sarabun and add an
``@font-face`` with a ``file://`` path for production. See CLAUDE.md."""

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
    return HTML(string=html, base_url=getattr(settings, "SITE_BASE_URL", None)).write_pdf()
