from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.utils import timezone

from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def test_daily_digest_task_sends_when_there_is_a_feed(user, membership, tenant) -> None:
    from apps.core.notifications import send_daily_digest
    from apps.crm.models import Lead

    with tenant_context(tenant):
        Lead.objects.create(name="ลีดใหม่ที่มอบให้คุณ", assigned_to=user)
    mail.outbox.clear()
    send_daily_digest.enqueue(tenant.pk, user.pk)
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert user.email in msg.to
    assert "สรุปงานวันนี้" in msg.subject
    assert any("text/html" in alt[1] for alt in getattr(msg, "alternatives", []))


def test_daily_digest_silent_when_nothing_to_say(user, membership, tenant) -> None:
    from apps.core.notifications import send_daily_digest

    mail.outbox.clear()
    send_daily_digest.enqueue(tenant.pk, user.pk)
    assert mail.outbox == []


def test_notify_quote_viewed_fires_once_on_first_view(user, tenant) -> None:
    from apps.quotes.models import DocStatus, DocType, SalesDocument
    from apps.quotes.services import record_quote_viewed

    with tenant_context(tenant):
        doc = SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            issue_date=date.today(),
            status=DocStatus.SENT,
            doc_number="QT-2569-7001",
            salesperson=user,
            sent_at=timezone.now(),
        )
        mail.outbox.clear()
        record_quote_viewed(doc, ip="1.2.3.4")
        assert len(mail.outbox) == 1
        assert "QT-2569-7001" in mail.outbox[0].subject
        # second view: no extra email
        record_quote_viewed(doc, ip="1.2.3.4")
        assert len(mail.outbox) == 1


def test_send_ar_reminders_command_enqueues_for_overdue_invoice(user, membership, tenant) -> None:
    from django.core.management import call_command

    from apps.billing import services
    from apps.crm.models import Contact, Customer
    from apps.quotes.models import DocStatus, DocType, LineType, SalesDocLine, SalesDocument

    with tenant_context(tenant):
        cust = Customer.objects.create(name="ลูกค้าค้างจ่าย")
        Contact.objects.create(customer=cust, name="ติดต่อ", email="contact@cust.test")
        q = SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            customer=cust,
            issue_date=date.today(),
            status=DocStatus.ACCEPTED,
        )
        SalesDocLine.objects.create(
            document=q,
            line_type=LineType.ITEM,
            description="ตู้",
            quantity=1,
            unit_price=Decimal("10000"),
            tax_type="vat7",
        )
        inv = services.create_invoice_from_quotation(q, user=user)
        inv.due_date = date.today() - timedelta(days=10)
        inv.salesperson = user
        inv.save(update_fields=["due_date", "salesperson"])
    mail.outbox.clear()
    call_command("send_ar_reminders")
    # ImmediateBackend runs the enqueued task synchronously → an email goes out
    assert len(mail.outbox) == 1
    assert inv.doc_number in mail.outbox[0].subject
