"""Enqueue AR-due reminders for invoices that are overdue or due within 3 days (all tenants).

Run on a schedule (cron, daily):

    uv run python manage.py send_ar_reminders

Per tenant: find INVOICE documents with a positive outstanding balance whose ``due_date`` is within
the next 3 days (or already past); enqueue ``send_ar_reminder`` for each (it emails the salesperson /
contact and LINE-texts the contact if configured).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.core.current_tenant import tenant_context
from apps.core.notifications import send_ar_reminder
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = "Enqueue payment reminders for overdue / soon-due invoices (all tenants)."

    def handle(self, *args, **options) -> None:
        from apps.billing.services import invoice_outstanding
        from apps.quotes.models import DocStatus, DocType, SalesDocument

        cutoff = date.today() + timedelta(days=3)
        enqueued = 0
        for tenant in Tenant.objects.filter(is_active=True):
            with tenant_context(tenant):
                invoices = SalesDocument.objects.filter(
                    doc_type=DocType.INVOICE,
                    due_date__isnull=False,
                    due_date__lte=cutoff,
                ).exclude(status=DocStatus.CANCELLED)
                for inv in invoices:
                    if invoice_outstanding(inv) > Decimal("0"):
                        send_ar_reminder.enqueue(inv.pk, tenant.pk)
                        enqueued += 1
        self.stdout.write(self.style.SUCCESS(f"Enqueued {enqueued} AR-reminder task(s)."))
