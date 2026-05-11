"""Expire quotations whose price-validity date has passed.

Run on a schedule (cron / a periodic task): READY or SENT quotations past their ``valid_until``
move to EXPIRED. Walks every active tenant (sets the tenant context per tenant — see CLAUDE.md §5).

    uv run python manage.py expire_quotations
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.core.current_tenant import tenant_context
from apps.quotes.services import expire_overdue_quotations
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = "Move READY/SENT quotations past their valid_until date to EXPIRED (all tenants)."

    def handle(self, *args, **options) -> None:
        total = 0
        for tenant in Tenant.objects.filter(is_active=True):
            with tenant_context(tenant):
                n = expire_overdue_quotations()
            if n:
                self.stdout.write(f"{tenant.slug}: expired {n}")
            total += n
        self.stdout.write(self.style.SUCCESS(f"Done — expired {total} quotation(s)."))
