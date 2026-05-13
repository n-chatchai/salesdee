"""Background tasks for billing (statement send, …). CLAUDE.md §4.5 — slow work off the request."""

from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMessage
from django.tasks import task

from apps.core.current_tenant import tenant_context
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
