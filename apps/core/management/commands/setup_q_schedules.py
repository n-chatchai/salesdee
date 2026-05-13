"""Idempotently create the django-q ``Schedule`` rows for salesdee's recurring jobs.

Run once after deploy (and re-run anytime the schedule list changes — it's a
``update_or_create`` keyed by name). The qcluster process picks up changes live.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django_q.models import Schedule

SCHEDULES = [
    # (name, function dotted path, cron expression Asia/Bangkok)
    (
        "salesdee.send_daily_digests",
        "django.core.management.call_command",
        "0 7 * * *",
        ("send_daily_digests",),
        "Daily 07:00 — per-user notification digest (apps.crm.management.commands.send_daily_digests).",
    ),
    (
        "salesdee.send_ar_reminders",
        "django.core.management.call_command",
        "30 8 * * *",
        ("send_ar_reminders",),
        "Daily 08:30 — AR aging reminders (apps.billing.management.commands.send_ar_reminders).",
    ),
    (
        "salesdee.expire_quotations",
        "django.core.management.call_command",
        "0 2 * * *",
        ("expire_quotations",),
        "Daily 02:00 — flip overdue READY/SENT quotations to EXPIRED.",
    ),
]


class Command(BaseCommand):
    help = "Idempotently create the django-q Schedule rows for recurring jobs."

    def handle(self, *args, **options):
        created = updated = 0
        for name, func, cron, fn_args, desc in SCHEDULES:
            obj, was_created = Schedule.objects.update_or_create(
                name=name,
                defaults={
                    "func": func,
                    "args": repr(fn_args),
                    "cron": cron,
                    "schedule_type": Schedule.CRON,
                    "hook": None,
                    "repeats": -1,
                },
            )
            created += int(was_created)
            updated += int(not was_created)
            self.stdout.write(f"{'+' if was_created else '~'} {name}  {cron}  — {desc}")
        self.stdout.write(self.style.SUCCESS(f"Done. {created} created, {updated} updated."))
