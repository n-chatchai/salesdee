"""The logged-in home dashboard (REQUIREMENTS.md §4.9 FR-9.1, plus win-rate / lost-reason bits).

``build_dashboard(user)`` returns a plain dict the ``core/home.html`` template renders. Every query
is tenant-scoped (the request middleware has the tenant active by the time this runs).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone


def _money(value: Decimal | int | None) -> Decimal:
    """An aggregate sum (or None) → a Decimal, defaulting to 0."""
    return value if isinstance(value, Decimal) else Decimal(value or 0)


def build_dashboard(request) -> dict:
    from apps.core.permissions import own_q
    from apps.quotes.models import DocStatus, DocType, SalesDocument

    from .models import (
        Deal,
        DealStatus,
        Lead,
        LeadStatus,
        PipelineStage,
        StageKind,
        Task,
        TaskStatus,
    )

    user = request.user
    own_deals = own_q(request, "owner")
    own_leads = own_q(request, "assigned_to")
    own_quotes = own_q(request, "salesperson")
    today = date.today()
    now = timezone.now()
    month_start = today.replace(day=1)
    soon = today + timedelta(days=7)
    since_90d = today - timedelta(days=90)

    # --- pipeline (open deals) ------------------------------------------------
    open_deals = Deal.objects.filter(own_deals, status=DealStatus.OPEN)
    open_value = _money(open_deals.aggregate(s=Sum("estimated_value"))["s"])
    open_count = open_deals.count()
    weighted = _money(
        open_deals.aggregate(
            s=Sum(
                ExpressionWrapper(
                    F("estimated_value") * F("probability") / 100.0,
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                )
            )
        )["s"]
    )
    stage_counts = {
        row["stage"]: row
        for row in open_deals.values("stage").annotate(n=Count("id"), v=Sum("estimated_value"))
    }
    stage_rows = [
        (
            stage,
            stage_counts.get(stage.pk, {}).get("n") or 0,
            _money(stage_counts.get(stage.pk, {}).get("v")),
        )
        for stage in PipelineStage.objects.filter(kind=StageKind.OPEN).order_by("order", "id")
    ]
    stale_deals = list(
        open_deals.filter(updated_at__lt=now - timedelta(days=21))
        .select_related("customer", "owner")
        .order_by("updated_at")[:8]
    )

    # --- this month: won / lost / win rate -----------------------------------
    closed_this_month = Deal.objects.filter(
        own_deals, status__in=[DealStatus.WON, DealStatus.LOST], closed_at__date__gte=month_start
    )
    won_qs = closed_this_month.filter(status=DealStatus.WON)
    won_count = won_qs.count()
    won_value = _money(won_qs.aggregate(s=Sum("estimated_value"))["s"])
    lost_count = closed_this_month.filter(status=DealStatus.LOST).count()
    closed_count = won_count + lost_count
    win_rate = round(won_count * 100 / closed_count) if closed_count else None
    lost_reasons = list(
        Deal.objects.filter(own_deals, status=DealStatus.LOST, closed_at__date__gte=since_90d)
        .exclude(lost_reason="")
        .values("lost_reason")
        .annotate(n=Count("id"))
        .order_by("-n")[:5]
    )

    # --- my tasks -------------------------------------------------------------
    my_open_tasks = Task.objects.filter(assignee=user, status=TaskStatus.OPEN)
    overdue_tasks = my_open_tasks.filter(due_at__lt=now).count()
    due_today_tasks = my_open_tasks.filter(due_at__date=today).count()
    upcoming_tasks = list(
        my_open_tasks.select_related("deal", "customer")
        .filter(due_at__date__lte=today + timedelta(days=2))
        .order_by("due_at")[:8]
    )

    # --- quotations -----------------------------------------------------------
    quotes = SalesDocument.objects.filter(own_quotes, doc_type=DocType.QUOTATION)
    awaiting = quotes.filter(status=DocStatus.SENT, customer_response="")
    awaiting_count = awaiting.count()
    awaiting_list = list(
        awaiting.select_related("customer", "salesperson").order_by("-sent_at")[:8]
    )
    expiring = (
        quotes.filter(
            status__in=[DocStatus.READY, DocStatus.SENT],
            valid_until__isnull=False,
            valid_until__gte=today,
            valid_until__lte=soon,
        )
        .select_related("customer")
        .order_by("valid_until")
    )
    expiring_count = expiring.count()
    expiring_list = list(expiring[:8])

    # --- new leads ------------------------------------------------------------
    new_leads = Lead.objects.filter(own_leads, status=LeadStatus.NEW)
    new_leads_count = new_leads.count()
    new_leads_recent = list(new_leads.order_by("-created_at")[:8])
    channel_counts = list(
        Lead.objects.filter(created_at__date__gte=month_start)
        .values("channel")
        .annotate(n=Count("id"))
        .order_by("-n")
    )

    # --- recent activities ----------------------------------------------------
    from .models import Activity

    recent_activities = list(
        Activity.objects.filter(Q(created_by=user) | Q(deal__owner=user))
        .select_related("deal", "lead", "customer")
        .order_by("-occurred_at")[:10]
    )

    # --- sales targets --------------------------------------------------------
    from .models import SalesTarget

    target = (
        SalesTarget.objects.filter(
            Q(salesperson=user) | Q(salesperson__isnull=True),
            year=today.year,
            month=today.month,
        )
        .order_by("-salesperson")
        .first()
    )
    target_amount = target.amount if target else 0
    target_percent = round(won_value * 100 / target_amount) if target_amount and won_value else 0

    return {
        "dash": True,
        "open_value": open_value,
        "open_count": open_count,
        "weighted_forecast": weighted,
        "stage_rows": stage_rows,
        "stale_deals": stale_deals,
        "won_count": won_count,
        "won_value": won_value,
        "lost_count": lost_count,
        "win_rate": win_rate,
        "lost_reasons": lost_reasons,
        "overdue_tasks": overdue_tasks,
        "due_today_tasks": due_today_tasks,
        "upcoming_tasks": upcoming_tasks,
        "awaiting_count": awaiting_count,
        "awaiting_list": awaiting_list,
        "expiring_count": expiring_count,
        "expiring_list": expiring_list,
        "new_leads_count": new_leads_count,
        "new_leads_recent": new_leads_recent,
        "channel_counts": channel_counts,
        "recent_activities": recent_activities,
        "target_amount": target_amount,
        "target_percent": target_percent,
        "now": now,
    }


def build_notifications(request) -> list[dict]:
    """A single feed of things needing the current user's attention. Reuses the same query shapes
    as ``build_dashboard``. Returns a list of dicts the ``core/notifications.html`` template renders.
    Tenant is active by the time this runs (middleware)."""
    from django.urls import reverse

    from apps.core.permissions import own_q
    from apps.integrations.models import Conversation, ConversationStatus
    from apps.quotes.models import DocStatus, DocType, SalesDocument

    from .models import Lead, LeadStatus, Task, TaskStatus

    user = request.user
    today = date.today()
    now = timezone.now()
    soon = today + timedelta(days=5)
    items: list[dict] = []

    my_open_tasks = Task.objects.filter(assignee=user, status=TaskStatus.OPEN).select_related(
        "deal", "customer"
    )
    for t in my_open_tasks.filter(due_at__lt=now).order_by("due_at")[:20]:
        items.append(
            {
                "icon": "i-check-square",
                "tone": "danger",
                "text": f"งานเลยกำหนด: {t.description or t.get_kind_display()}",
                "url": reverse("crm:deal_detail", args=[t.deal_id])
                if t.deal_id
                else reverse("crm:tasks"),
                "when": t.due_at,
            }
        )
    for t in my_open_tasks.filter(due_at__date=today).order_by("due_at")[:20]:
        items.append(
            {
                "icon": "i-check-square",
                "tone": "warn",
                "text": f"งานวันนี้: {t.description or t.get_kind_display()}",
                "url": reverse("crm:deal_detail", args=[t.deal_id])
                if t.deal_id
                else reverse("crm:tasks"),
                "when": t.due_at,
            }
        )

    quotes = SalesDocument.objects.filter(own_q(request, "salesperson"), doc_type=DocType.QUOTATION)
    for q in (
        quotes.filter(status=DocStatus.SENT, customer_response="")
        .select_related("customer")
        .order_by("-sent_at")[:20]
    ):
        items.append(
            {
                "icon": "i-file-text",
                "tone": "",
                "text": f"รอลูกค้าตอบรับ: {q.doc_number or q} · {q.customer.name if q.customer else ''}",
                "url": reverse("quotes:quotation_detail", args=[q.pk]),
                "when": q.sent_at,
            }
        )
    for q in (
        quotes.filter(
            status__in=[DocStatus.READY, DocStatus.SENT],
            valid_until__isnull=False,
            valid_until__gte=today,
            valid_until__lte=soon,
        )
        .select_related("customer")
        .order_by("valid_until")[:20]
    ):
        items.append(
            {
                "icon": "i-file-text",
                "tone": "warn",
                "text": f"ใบเสนอราคาใกล้หมดอายุ ({q.valid_until}): {q.doc_number or q}",
                "url": reverse("quotes:quotation_detail", args=[q.pk]),
                "when": q.valid_until,
            }
        )

    for c in (
        Conversation.objects.filter(status=ConversationStatus.OPEN)
        .filter(Q(assigned_to__isnull=True) | Q(unread_count__gt=0))
        .order_by("-last_message_at")[:20]
    ):
        items.append(
            {
                "icon": "i-inbox",
                "tone": "ai" if c.assigned_to_id is None else "",
                "text": ("แชทยังไม่มีผู้รับผิดชอบ: " if c.assigned_to_id is None else "แชทมีข้อความใหม่: ")
                + (c.display_name or str(c)),
                "url": reverse("integrations:conversation", args=[c.pk]),
                "when": c.last_message_at,
            }
        )

    for lead in Lead.objects.filter(
        own_q(request, "assigned_to"), status=LeadStatus.NEW, assigned_to=user
    ).order_by("-created_at")[:20]:
        items.append(
            {
                "icon": "i-target",
                "tone": "",
                "text": f"ลีดใหม่ที่มอบหมายให้คุณ: {lead.name or lead.company_name}",
                "url": reverse("crm:lead_detail", args=[lead.pk]),
                "when": lead.created_at,
            }
        )

    items.sort(key=lambda i: (i.get("when") is None, _as_dt(i.get("when"))), reverse=False)
    # Most urgent (oldest due / oldest sent) first; danger items already near the top by time.
    return items


def _as_dt(value):
    """Coerce a date/datetime/None to a sortable datetime."""
    from datetime import datetime

    if value is None:
        return datetime.max
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return datetime.combine(value, datetime.min.time())
