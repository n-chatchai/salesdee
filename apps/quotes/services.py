"""Quotation services: document-number allocation, totals engine, create-from-deal.
See CLAUDE.md §4 (decimal money, transactional doc numbers, snapshot rates)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.catalog.models import TaxType
from apps.core.utils import baht_text
from apps.core.utils.thai_dates import to_be_year

from .models import (
    DiscountKind,
    DocStatus,
    DocType,
    DocumentNumberSequence,
    LineType,
    SalesDocument,
)

VAT_RATE = Decimal("0.07")
_Q2 = Decimal("0.01")


def _q2(value) -> Decimal:
    return Decimal(value).quantize(_Q2, rounding=ROUND_HALF_UP)


@transaction.atomic
def next_document_number(doc_type: str, *, prefix: str, year: int | None = None) -> str:
    """Allocate the next gap-free number for (current tenant, doc_type, year).

    Caller must be inside a tenant context. ``year`` defaults to the current Buddhist year.
    Uses ``select_for_update`` on the sequence row; ``get_or_create`` recovers from the rare
    first-allocation race.
    """
    if year is None:
        year = to_be_year(date.today().year)
    seq, _ = DocumentNumberSequence.objects.select_for_update().get_or_create(
        doc_type=doc_type, year=year, defaults={"last_number": 0}
    )
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"{prefix}-{year}-{seq.last_number:04d}"


def create_quotation_from_deal(deal, *, salesperson=None) -> SalesDocument:
    """Create a draft quotation linked to ``deal`` (caller must be in the deal's tenant)."""
    today = date.today()
    doc = SalesDocument.objects.create(
        doc_type=DocType.QUOTATION,
        deal=deal,
        customer=deal.customer,
        contact=deal.contact,
        salesperson=salesperson,
        issue_date=today,
        valid_until=today + timedelta(days=30),
        reference=deal.name,
        status=DocStatus.DRAFT,
    )
    doc.doc_number = next_document_number(DocType.QUOTATION, prefix="QT")
    doc.save()
    return doc


# --- Totals engine ------------------------------------------------------------
@dataclass
class GroupTotal:
    label: str
    lines: list
    subtotal: Decimal


@dataclass
class DocumentTotals:
    groups: list  # of GroupTotal
    subtotal: Decimal
    end_discount: Decimal
    after_discount: Decimal
    base_vat7: Decimal
    base_vat0: Decimal
    base_exempt: Decimal
    base_none: Decimal
    vat_amount: Decimal
    grand_total: Decimal
    withholding_estimate: Decimal
    net_expected: Decimal
    amount_in_words: str
    has_zero_rated: bool


def compute_document_totals(document: SalesDocument) -> DocumentTotals:
    """Subtotal → end-of-bill discount (allocated proportionally) → VAT bases per rate → VAT →
    grand total + withholding estimate + BahtText. EXCLUSIVE pricing only for now (TODO: inclusive)."""
    lines = list(document.lines.all())
    item_lines = [ln for ln in lines if ln.line_type == LineType.ITEM]
    nets: dict[int, Decimal] = {ln.pk: ln.amount for ln in item_lines}
    subtotal = sum(nets.values(), Decimal(0))

    if document.end_discount_kind == DiscountKind.PERCENT:
        end_discount = subtotal * Decimal(document.end_discount_value) / 100
    else:
        end_discount = Decimal(document.end_discount_value)
    end_discount = min(end_discount, subtotal) if subtotal > 0 else Decimal(0)
    after_discount = subtotal - end_discount

    buckets: dict[str, Decimal] = {
        t: Decimal(0) for t in (TaxType.VAT7, TaxType.VAT0, TaxType.EXEMPT, TaxType.NONE)
    }
    withholding = Decimal(0)
    for ln in item_lines:
        net = nets[ln.pk]
        alloc = (net / subtotal * end_discount) if subtotal > 0 else Decimal(0)
        post = net - alloc
        buckets[ln.tax_type] = buckets.get(ln.tax_type, Decimal(0)) + post
        withholding += post * Decimal(ln.withholding_rate) / 100

    vat_amount = buckets[TaxType.VAT7] * VAT_RATE
    grand_total = _q2(after_discount + vat_amount)
    withholding = _q2(withholding)
    net_expected = grand_total - withholding

    # groups for display (first-seen order)
    order: list[str] = []
    grouped: dict[str, list] = {}
    for ln in lines:
        label = ln.group_label or ""
        if label not in grouped:
            grouped[label] = []
            order.append(label)
        grouped[label].append(ln)
    groups = [
        GroupTotal(
            label=label,
            lines=grouped[label],
            subtotal=_q2(
                sum(
                    (
                        nets.get(ln.pk, Decimal(0))
                        for ln in grouped[label]
                        if ln.line_type == LineType.ITEM
                    ),
                    Decimal(0),
                )
            ),
        )
        for label in order
    ]

    return DocumentTotals(
        groups=groups,
        subtotal=_q2(subtotal),
        end_discount=_q2(end_discount),
        after_discount=_q2(after_discount),
        base_vat7=_q2(buckets[TaxType.VAT7]),
        base_vat0=_q2(buckets[TaxType.VAT0]),
        base_exempt=_q2(buckets[TaxType.EXEMPT]),
        base_none=_q2(buckets[TaxType.NONE]),
        vat_amount=_q2(vat_amount),
        grand_total=grand_total,
        withholding_estimate=withholding,
        net_expected=_q2(net_expected),
        amount_in_words=baht_text(grand_total),
        has_zero_rated=bool(
            buckets[TaxType.VAT0] or buckets[TaxType.EXEMPT] or buckets[TaxType.NONE]
        ),
    )
