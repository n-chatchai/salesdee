from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.core import mail

from apps.billing import services
from apps.billing.tasks import send_billing_doc_email
from apps.core.current_tenant import tenant_context
from apps.crm.models import Contact, Customer
from apps.quotes.models import DocStatus, DocType, LineType, SalesDocLine, SalesDocument

pytestmark = pytest.mark.django_db


def test_send_billing_doc_email_attaches_pdf(tenant) -> None:
    with tenant_context(tenant):
        cust = Customer.objects.create(name="ลูกค้าทดสอบ")
        Contact.objects.create(customer=cust, name="ติดต่อ", email="c@example.com")
        q = SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            customer=cust,
            issue_date=date.today(),
            status=DocStatus.ACCEPTED,
        )
        SalesDocLine.objects.create(
            document=q,
            line_type=LineType.ITEM,
            description="ของ",
            quantity=1,
            unit_price=Decimal("1000"),
            tax_type="vat7",
        )
        inv = services.create_invoice_from_quotation(q)
        tax = services.issue_tax_invoice(inv)
    mail.outbox.clear()
    send_billing_doc_email.enqueue(
        tax.pk, tenant.pk, recipient_email="c@example.com", kind="tax_invoice"
    )
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert tax.doc_number in msg.subject
    # one PDF attachment
    assert len(msg.attachments) == 1
    name, content, mime = msg.attachments[0]
    assert mime == "application/pdf"
    assert content.startswith(b"%PDF")
