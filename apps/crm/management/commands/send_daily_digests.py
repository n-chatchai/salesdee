"""Enqueue a daily-digest email for every active member of every active tenant.

Run on a schedule (cron, ~07:00 Asia/Bangkok):

    uv run python manage.py send_daily_digests

Each (tenant, member-with-email) pair gets a ``send_daily_digest`` task enqueued; the task itself
activates the tenant context, builds the member's feed, and only sends if there's something to say.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.accounts.models import Membership
from apps.core.notifications import send_daily_digest
from apps.tenants.models import Tenant


class Command(BaseCommand):
    help = "Enqueue daily-digest emails for all active members of all active tenants."

    def handle(self, *args, **options) -> None:
        enqueued = 0
        for tenant in Tenant.objects.filter(is_active=True):
            members = (
                Membership.objects.filter(tenant=tenant, is_active=True, user__is_active=True)
                .exclude(user__email="")
                .select_related("user")
            )
            for m in members:
                send_daily_digest.enqueue(tenant.pk, m.user_id)
                enqueued += 1
        self.stdout.write(self.style.SUCCESS(f"Enqueued {enqueued} daily-digest task(s)."))
