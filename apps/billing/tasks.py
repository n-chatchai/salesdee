"""Background tasks for billing (statement send, doc-send via email/LINE).
CLAUDE.md §4.5 — slow work off the request."""

from __future__ import annotations

import contextlib

from django.conf import settings
from django.core.mail import EmailMessage

from apps.core.current_tenant import tenant_context
from apps.core.tasks import task
from apps.tenants.models import Tenant


@task()
def send_customer_statement_email(
    customer_id: int, tenant_id: int, *, recipient_email: str
) -> None:
    """Render the customer-statement PDF and email it to ``recipient_email``."""
    tenant = Tenant.objects.filter(pk=tenant_id).first()
    if tenant is None or not recipient_email:
        return
    with tenant_context(tenant):
        from apps.crm.models import Customer

        from .pdf import render_customer_statement_pdf
        from .services import customer_statement

        customer = Customer.objects.filter(pk=customer_id).first()
        if customer is None:
            return
        data = customer_statement(customer)
        pdf = render_customer_statement_pdf(data, customer=customer)
        msg = EmailMessage(
            subject=f"ใบแจ้งยอด — {customer.name}",
            body=(f"เรียนลูกค้า {customer.name}\n\nกรุณาดูใบแจ้งยอดล่าสุดในไฟล์แนบ\n\nระบบ salesdee"),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
        )
        msg.attach(f"statement-{customer.pk}.pdf", pdf, "application/pdf")
        msg.send(fail_silently=True)


_DOC_RENDERERS = {
    "tax_invoice": ("render_tax_invoice_pdf", "ใบกำกับภาษี"),
    "receipt": ("render_receipt_pdf", "ใบเสร็จรับเงิน"),
    "credit_note": ("render_credit_note_pdf", "ใบลดหนี้"),
    "debit_note": ("render_debit_note_pdf", "ใบเพิ่มหนี้"),
}


@task()
def send_billing_doc_email(
    document_id: int, tenant_id: int, *, recipient_email: str, kind: str
) -> None:
    """Render a billing PDF and email it as an attachment. ``kind`` ∈ ``_DOC_RENDERERS``."""
    tenant = Tenant.objects.filter(pk=tenant_id).first()
    if tenant is None or kind not in _DOC_RENDERERS or not recipient_email:
        return
    with tenant_context(tenant):
        from apps.quotes.models import SalesDocument

        from . import pdf as pdf_mod

        doc = SalesDocument.objects.filter(pk=document_id).first()
        if doc is None:
            return
        renderer_name, label = _DOC_RENDERERS[kind]
        renderer = getattr(pdf_mod, renderer_name)
        data = renderer(doc)
        msg = EmailMessage(
            subject=f"{label} {doc.doc_number}",
            body=(f"กรุณาดู{label}เลขที่ {doc.doc_number} ในไฟล์แนบ\n\nระบบ salesdee"),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
        )
        msg.attach(f"{doc.doc_number or kind}.pdf", data, "application/pdf")
        msg.send(fail_silently=True)


@task()
def send_billing_doc_line(
    document_id: int, tenant_id: int, *, recipient: str, kind: str, pdf_url: str = ""
) -> None:
    """Short LINE message announcing a billing doc — best-effort; no-ops if LINE isn't configured."""
    tenant = Tenant.objects.filter(pk=tenant_id).first()
    if tenant is None or not recipient or kind not in _DOC_RENDERERS:
        return
    with tenant_context(tenant):
        from apps.integrations import line as line_mod
        from apps.quotes.models import SalesDocument

        doc = SalesDocument.objects.filter(pk=document_id).first()
        if doc is None or not line_mod.line_is_configured():
            return
        _, label = _DOC_RENDERERS[kind]
        text = f"ส่ง{label}เลขที่ {doc.doc_number} แล้ว"
        if pdf_url:
            text += f"\nเปิดดู: {pdf_url}"
        with contextlib.suppress(Exception):  # best-effort
            line_mod.push_text(recipient, text)
