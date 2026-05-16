"""Home queue · feeds the inbox-style list on `/` (frame d.1, d.2).

Builds a unified list of items that need the salesperson's attention right now:
SalesDocuments in DRAFT / SENT (waiting for response or about to expire) +
new Leads not yet quoted. Each entry is normalised to a uniform shape the template
renders as an `.h-row`."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone


@dataclass
class QueueItem:
    key: str  # unique selector for this row (e.g. "q:42")
    name: str  # customer / lead display name
    company: str  # company name (or blank)
    context: str  # short context line (project, reference, last message)
    age_label: str  # "3 ชม", "2 วัน", "เหลือ 5 วัน"
    age_kind: str  # "", "stale", "critical"
    source: str  # "line" | "web" | "email" | "manual"
    source_letter: str  # avatar source badge text (L / W / E / M)
    status: str  # "new" | "waiting" | "expiring"
    status_label: str  # display label (รับเรื่องใหม่ / รอตอบ / ใกล้หมดอายุ)
    amount: str  # "฿185K" or ""
    url: str  # link to underlying object detail page
    initial: str  # avatar single-char letter


def _age(then) -> tuple[str, str]:
    """Return (label, kind). `kind` ∈ {'', 'stale', 'critical'}."""
    if then is None:
        return ("", "")
    now = timezone.now()
    if hasattr(then, "tzinfo"):
        delta = now - then
    else:
        delta = now.date() - then
        delta = timedelta(days=delta.days)
    days = delta.days
    if days >= 1:
        label = f"{days} วัน"
        kind = "stale" if days < 3 else "critical"
    else:
        hours = delta.seconds // 3600
        if hours >= 1:
            label = f"{hours} ชม"
            kind = ""
        else:
            label = f"{max(1, delta.seconds // 60)} นาที"
            kind = ""
    return (label, kind)


def _expiry_age(valid_until) -> tuple[str, str]:
    if valid_until is None:
        return ("", "")
    days = (valid_until - date.today()).days
    if days < 0:
        return (f"หมดอายุ {abs(days)} วันแล้ว", "critical")
    if days <= 2:
        return (f"เหลือ {days} วัน", "critical")
    if days <= 7:
        return (f"เหลือ {days} วัน", "stale")
    return (f"เหลือ {days} วัน", "")


def _doc_total(doc) -> int | None:
    """Best-effort SalesDocument total · uses compute_document_totals lazily.
    Returns int (THB rounded) or None when computation fails."""
    try:
        from apps.quotes.services import compute_document_totals

        return int(compute_document_totals(doc).grand_total)
    except Exception:  # noqa: BLE001 — never break the queue over a totals issue
        return None


def _amount_label(value) -> str:
    if not value:
        return ""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return ""
    if v >= 1_000_000:
        return f"฿{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"฿{v // 1_000}K"
    return f"฿{v}"


def _source_letter(source: str) -> str:
    return {"line": "ล", "web": "W", "email": "E", "manual": "M"}.get(source, "M")


def build_home_queue(request: HttpRequest, *, selected_key: str | None = None) -> dict:
    """Returns {queue, active, counts, filter}. `active` is the QueueItem matching
    `selected_key`, or the first row when none specified."""
    from apps.quotes.models import DocStatus, SalesDocument

    items: list[QueueItem] = []
    today = date.today()
    soon = today + timedelta(days=14)

    qs = (
        SalesDocument.objects.filter(
            status__in=[
                DocStatus.REQUEST,
                DocStatus.DRAFT,
                DocStatus.SENT,
                DocStatus.PENDING_APPROVAL,
                DocStatus.READY,
            ]
        )
        .exclude(doc_type__in=["invoice", "tax_invoice", "receipt", "credit_note", "debit_note"])
        .select_related("customer")
        .order_by("-created_at")[:40]
    )
    for doc in qs:
        is_sent = doc.status == DocStatus.SENT
        if is_sent and doc.valid_until and doc.valid_until <= soon:
            age_label, age_kind = _expiry_age(doc.valid_until)
            status = "expiring"
            status_label = "ใกล้หมดอายุ"
        elif is_sent:
            age_label, age_kind = _age(doc.sent_at or doc.created_at)
            status = "waiting"
            status_label = "รอตอบ"
        else:
            age_label, age_kind = _age(doc.created_at)
            status = "new"
            status_label = "รับเรื่องใหม่"

        source = doc.source or ("line" if doc.source_conversation_id else "manual")
        customer = doc.customer
        cust_name = customer.name if customer else "ลูกค้าใหม่"
        company = getattr(customer, "company_name", "") if customer else ""
        context_bits = []
        if doc.doc_number:
            context_bits.append(f"<em>{doc.doc_number}</em>")
        if doc.reference:
            context_bits.append(doc.reference)
        if is_sent and doc.view_count:
            context_bits.append(f"เปิด <strong>{doc.view_count} ครั้ง</strong>")

        items.append(
            QueueItem(
                key=f"q:{doc.pk}",
                name=cust_name,
                company=company,
                context=" · ".join(context_bits) or "—",
                age_label=age_label,
                age_kind=age_kind,
                source=source,
                source_letter=_source_letter(source),
                status=status,
                status_label=status_label,
                amount=_amount_label(_doc_total(doc)),
                url=reverse("quotes:quotation_detail", args=[doc.pk]),
                initial=(cust_name[:1] or "?").upper(),
            )
        )

    counts = {
        "all": len(items),
        "new": sum(1 for i in items if i.status == "new"),
        "waiting": sum(1 for i in items if i.status == "waiting"),
        "expiring": sum(1 for i in items if i.status == "expiring"),
    }

    filt = (request.GET.get("filter") or "").strip()
    if filt in {"new", "waiting", "expiring"}:
        filtered: Iterable[QueueItem] = [i for i in items if i.status == filt]
    else:
        filt = "all"
        filtered = items
    filtered_list = list(filtered)

    active = None
    if selected_key:
        active = next((i for i in filtered_list if i.key == selected_key), None)
    if active is None and filtered_list:
        active = filtered_list[0]

    active_doc = None
    if active and active.key.startswith("q:"):
        active_doc = (
            SalesDocument.objects.filter(pk=int(active.key.split(":", 1)[1]))
            .select_related("customer")
            .prefetch_related("lines")
            .first()
        )

    return {
        "queue": filtered_list,
        "queue_all": items,
        "active": active,
        "active_doc": active_doc,
        "counts": counts,
        "filter": filt,
    }
