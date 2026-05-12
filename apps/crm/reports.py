"""Sales reports for the /crm/reports/ page (REQUIREMENTS.md §4.9 FR-9.2/9.3/9.4/9.5).

``build_reports(start, end)`` returns a plain dict the template renders. Everything is tenant-scoped
(the request middleware has the tenant active). "Won value" uses ``Deal.estimated_value``.
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth


def build_reports(start: date, end: date) -> dict:
    from apps.quotes.models import DocStatus, DocType, SalesDocument

    from .models import Deal, DealStatus, Lead, LeadChannel, SalesTarget

    won = Deal.objects.filter(
        status=DealStatus.WON, closed_at__date__gte=start, closed_at__date__lte=end
    )
    quotes = SalesDocument.objects.filter(
        doc_type=DocType.QUOTATION, issue_date__gte=start, issue_date__lte=end
    )
    responded_statuses = [DocStatus.SENT, DocStatus.ACCEPTED, DocStatus.REJECTED, DocStatus.EXPIRED]

    # --- by salesperson: won deals + quotation conversion + this month's target -----------------
    won_by_user = {
        r["owner"]: r for r in won.values("owner").annotate(n=Count("id"), v=Sum("estimated_value"))
    }
    quotes_by_user = {
        r["salesperson"]: r
        for r in quotes.values("salesperson").annotate(
            sent=Count("id", filter=Q(status__in=responded_statuses)),
            accepted=Count("id", filter=Q(status=DocStatus.ACCEPTED)),
        )
    }
    today = date.today()
    targets = {
        t.salesperson_id: t.amount
        for t in SalesTarget.objects.filter(year=today.year, month=today.month)
    }
    user_ids = {uid for uid in (set(won_by_user) | set(quotes_by_user)) if uid is not None}
    users = {u.pk: u for u in get_user_model().objects.filter(pk__in=user_ids)}
    by_salesperson = []
    for uid in user_ids:
        w = won_by_user.get(uid, {})
        q = quotes_by_user.get(uid, {})
        sent = q.get("sent") or 0
        accepted = q.get("accepted") or 0
        by_salesperson.append(
            {
                "name": users[uid].get_full_name() if uid in users else "—",
                "won_count": w.get("n") or 0,
                "won_value": w.get("v") or 0,
                "quotes_sent": sent,
                "quotes_accepted": accepted,
                "conv_rate": round(accepted * 100 / sent) if sent else None,
                "target": targets.get(uid),
            }
        )
    by_salesperson.sort(key=lambda r: r["won_value"] or 0, reverse=True)

    # --- won deals by month (within the range, by close month) ----------------------------------
    by_month = list(
        won.annotate(m=TruncMonth("closed_at"))
        .values("m")
        .annotate(n=Count("id"), v=Sum("estimated_value"))
        .order_by("m")
    )

    # --- by lead channel: leads created + won-deal value --------------------------------------
    lead_counts = {
        r["channel"]: r["n"]
        for r in Lead.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
        .values("channel")
        .annotate(n=Count("id"))
    }
    deal_won = {
        r["channel"]: r
        for r in won.values("channel").annotate(n=Count("id"), v=Sum("estimated_value"))
    }
    channel_label = dict(LeadChannel.choices)
    by_channel = [
        {
            "label": channel_label.get(ch) or (ch or "—"),
            "leads": lead_counts.get(ch, 0),
            "won_deals": deal_won.get(ch, {}).get("n") or 0,
            "won_value": deal_won.get(ch, {}).get("v") or 0,
        }
        for ch in sorted(set(lead_counts) | set(deal_won))
    ]

    # --- lost-reason breakdown ------------------------------------------------------------------
    lost_by_reason = list(
        Deal.objects.filter(
            status=DealStatus.LOST, closed_at__date__gte=start, closed_at__date__lte=end
        )
        .exclude(lost_reason="")
        .values("lost_reason")
        .annotate(n=Count("id"))
        .order_by("-n")
    )

    return {
        "start": start,
        "end": end,
        "by_salesperson": by_salesperson,
        "team_target": targets.get(None),
        "by_month": by_month,
        "by_channel": by_channel,
        "lost_by_reason": lost_by_reason,
        "totals": {
            "won_count": won.count(),
            "won_value": won.aggregate(s=Sum("estimated_value"))["s"] or 0,
            "quotes_count": quotes.count(),
        },
    }
