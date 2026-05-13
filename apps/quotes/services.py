"""Quotation services: document-number allocation, totals engine, create-from-deal.
See CLAUDE.md §4 (decimal money, transactional doc numbers, snapshot rates)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import TaxType
from apps.core.utils import baht_text
from apps.core.utils.thai_dates import to_be_year

from .models import (
    CustomerResponse,
    DiscountKind,
    DocStatus,
    DocType,
    DocumentNumberSequence,
    LineType,
    PriceMode,
    QuotationShareLink,
    SalesDocLine,
    SalesDocument,
)


class WorkflowError(Exception):
    """A document status transition was attempted that isn't allowed from the current state."""


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


def create_quotation_from_ai_draft(
    draft: dict, *, salesperson=None, reference: str = "", deal=None
) -> SalesDocument:
    """Build a DRAFT quotation from an AI-extracted draft (see apps.integrations.ai). ``draft`` is
    ``{customer_name?, notes?, lines: [{product_code?, description, quantity, unit_price?}]}``.
    Lines that name a catalog code get linked (tax/unit/price filled from the product); the
    salesperson reviews & adjusts everything afterwards. Caller must be in the tenant's context."""
    from apps.catalog.models import Product

    today = date.today()
    doc = SalesDocument.objects.create(
        doc_type=DocType.QUOTATION,
        deal=deal,
        customer=deal.customer if deal is not None else None,
        contact=deal.contact if deal is not None else None,
        salesperson=salesperson,
        issue_date=today,
        valid_until=today + timedelta(days=30),
        reference=reference or (draft.get("customer_name") or "").strip(),
        notes=(draft.get("notes") or "").strip(),
        status=DocStatus.DRAFT,
    )
    doc.doc_number = next_document_number(DocType.QUOTATION, prefix="QT")
    doc.save()
    products = {p.code: p for p in Product.objects.filter(is_active=True).exclude(code="")}
    position = 0
    for item in draft.get("lines") or []:
        description = (item.get("description") or "").strip()
        product = products.get((item.get("product_code") or "").strip()) or None
        if not description and product is None:
            continue
        position += 1
        try:
            quantity = Decimal(str(item.get("quantity") or 1))
            unit_price = Decimal(str(item.get("unit_price") or 0))
        except (ArithmeticError, ValueError, TypeError):
            quantity, unit_price = Decimal(1), Decimal(0)
        line = SalesDocLine(
            document=doc,
            position=position,
            line_type=LineType.ITEM,
            description=description,
            quantity=quantity if quantity > 0 else Decimal(1),
            unit_price=unit_price if unit_price >= 0 else Decimal(0),
            product=product,
        )
        apply_catalog_defaults(
            line
        )  # fills tax/unit (always) + price/desc/dims/material (if blank)
        line.save()
    return doc


# --- Lines ---------------------------------------------------------------------
def apply_catalog_defaults(line) -> None:
    """When a line is linked to a catalog product/variant, take the product's tax type & unit as
    authoritative, and fill price / description / dimensions / material when the line leaves them blank."""
    product = line.product
    variant = line.variant
    if variant is not None and product is None:
        product = variant.product
        line.product = product
    if product is None:
        return
    line.tax_type = product.tax_type
    line.unit = product.unit
    if not line.unit_price:
        line.unit_price = (
            variant.price if variant is not None and variant.price else product.default_price
        ) or 0
    if not line.description.strip():
        line.description = (
            f"{product.name} — {variant.name}" if variant is not None else product.name
        )
    if not line.dimensions and product.dimensions:
        line.dimensions = product.dimensions
    if not line.material and product.material:
        line.material = product.material


# --- Sharing / customer response ---------------------------------------------
def get_or_create_share_link(
    document: SalesDocument, *, created_by=None, days: int = 30
) -> QuotationShareLink:
    """Return the document's current valid share link, creating one if there isn't one."""
    link = (
        QuotationShareLink.objects.filter(document=document, revoked=False)
        .order_by("-created_at")
        .first()
    )
    if link is not None and link.is_valid():
        return link
    return QuotationShareLink.objects.create(
        tenant_id=document.tenant_id,
        document=document,
        token=secrets.token_urlsafe(24),
        expires_at=timezone.now() + timedelta(days=days),
        created_by=created_by,
    )


def mark_sent(document: SalesDocument, *, user=None) -> None:
    """Stamp a quotation as sent (READY → SENT) and set ``sent_at``. Idempotent for a resend.
    On the actual READY → SENT transition, freeze a revision snapshot (REQUIREMENTS.md §4.7).
    The caller (quotes.views.quotation_send) is responsible for getting it to READY first."""
    first_send = document.status == DocStatus.READY
    if first_send:
        document.status = DocStatus.SENT
    document.sent_at = document.sent_at or timezone.now()
    document.save()
    if first_send:
        record_revision(document, user=user)


def record_quote_viewed(document: SalesDocument, *, ip: str | None = None) -> None:
    """Count a customer opening the public share link (REQUIREMENTS.md §4.8). ``ip`` is currently
    unused beyond being available for a future per-open audit row; we keep first/last/count here."""
    now = timezone.now()
    first_view = document.first_viewed_at is None
    if first_view:
        document.first_viewed_at = now
    document.last_viewed_at = now
    document.view_count = (document.view_count or 0) + 1
    document.save(update_fields=["first_viewed_at", "last_viewed_at", "view_count"])
    if first_view:
        from apps.core.notifications import notify_quote_viewed

        notify_quote_viewed.enqueue(document.pk, document.tenant_id)


def record_customer_response(
    document: SalesDocument,
    *,
    response: str,
    signed_name: str = "",
    note: str = "",
    ip: str | None = None,
) -> None:
    """Record the customer's accept / request-changes / reject from the public share link."""
    document.customer_response = response
    document.customer_signed_name = signed_name
    document.customer_response_note = note
    document.customer_responded_at = timezone.now()
    document.customer_response_ip = ip
    if response == CustomerResponse.ACCEPTED:
        document.status = DocStatus.ACCEPTED
    elif response == CustomerResponse.REJECTED:
        document.status = DocStatus.REJECTED
    # CHANGES -> stays SENT; the note tells the salesperson what to revise
    document.save()


# --- Revisions ---------------------------------------------------------------
def snapshot_document(document: SalesDocument) -> dict:
    """A self-contained JSON copy of a quotation (header + lines + computed totals) — what gets
    frozen into a ``QuotationRevision`` so old versions stay viewable after the live doc changes."""
    totals = compute_document_totals(document)
    customer = document.customer
    contact = document.contact
    salesperson = document.salesperson
    return {
        "doc_number": document.doc_number,
        "revision": document.revision,
        "issue_date": document.issue_date.isoformat() if document.issue_date else None,
        "valid_until": document.valid_until.isoformat() if document.valid_until else None,
        "sent_at": document.sent_at.isoformat() if document.sent_at else None,
        "customer": customer.name if customer else "",
        "contact": contact.name if contact else "",
        "reference": document.reference,
        "salesperson": salesperson.get_full_name() if salesperson else "",
        "price_mode": document.price_mode,
        "end_discount_kind": document.end_discount_kind,
        "end_discount_value": str(document.end_discount_value),
        "payment_terms": document.payment_terms,
        "lead_time": document.lead_time,
        "warranty": document.warranty,
        "notes": document.notes,
        "lines": [
            {
                "group_label": ln.group_label,
                "line_type": ln.line_type,
                "code": ln.product.code if ln.product else "",
                "description": ln.description,
                "dimensions": ln.dimensions,
                "material": ln.material,
                "quantity": str(ln.quantity),
                "unit": ln.unit,
                "unit_price": str(ln.unit_price),
                "discount_kind": ln.discount_kind,
                "discount_value": str(ln.discount_value),
                "tax_type": ln.tax_type,
                "withholding_rate": str(ln.withholding_rate),
                "amount": str(ln.amount),
            }
            for ln in document.lines.all()
        ],
        "totals": {
            "subtotal": str(totals.subtotal),
            "end_discount": str(totals.end_discount),
            "after_discount": str(totals.after_discount),
            "vat_amount": str(totals.vat_amount),
            "grand_total": str(totals.grand_total),
            "withholding_estimate": str(totals.withholding_estimate),
            "net_expected": str(totals.net_expected),
            "amount_in_words": totals.amount_in_words,
        },
    }


def record_revision(document: SalesDocument, *, user=None) -> None:
    """Freeze a snapshot of ``document`` at its current revision number (no-op-safe to re-run)."""
    from .models import QuotationRevision

    QuotationRevision.objects.update_or_create(
        document=document,
        revision=document.revision,
        defaults={
            "snapshot": snapshot_document(document),
            "reason": document.revision_note,
            "changed_by": user if getattr(user, "is_authenticated", False) else None,
        },
    )


# --- Document lifecycle: submit / approve / cancel / reopen / expire ----------
def _membership(user, tenant_id):
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    from apps.accounts.models import Membership

    return Membership.objects.filter(user=user, tenant_id=tenant_id, is_active=True).first()


def can_approve(user, tenant_id) -> bool:
    """Owners and managers may approve over-cap discounts (REQUIREMENTS.md §4.15)."""
    from apps.accounts.models import Role

    m = _membership(user, tenant_id)
    return m is not None and m.role in (Role.OWNER, Role.MANAGER)


def _line_discount_percent(line) -> Decimal:
    if line.discount_kind == DiscountKind.PERCENT:
        return Decimal(line.discount_value)
    base = Decimal(line.quantity) * Decimal(line.unit_price)
    return (Decimal(line.discount_value) / base * 100) if base > 0 else Decimal(0)


def discount_exceeds_cap(document: SalesDocument, *, user) -> bool:
    """True if this quotation needs manager approval given ``user``'s authority — i.e. any line or
    end-of-bill discount exceeds their ``max_discount_percent``, or the grand total exceeds their
    ``approval_limit``. Owners/managers (and users with no membership on record) never need it."""
    from apps.accounts.models import Role

    m = _membership(user, document.tenant_id)
    if m is None or m.role in (Role.OWNER, Role.MANAGER):
        return False
    item_lines = [ln for ln in document.lines.all() if ln.line_type == LineType.ITEM]
    worst_pct = max((_line_discount_percent(ln) for ln in item_lines), default=Decimal(0))
    subtotal = sum((ln.amount for ln in item_lines), Decimal(0))
    if document.end_discount_kind == DiscountKind.PERCENT:
        end_pct = Decimal(document.end_discount_value)
    elif subtotal > 0:
        end_pct = Decimal(document.end_discount_value) / subtotal * 100
    else:
        end_pct = Decimal(0)
    worst_pct = max(worst_pct, end_pct)
    if m.max_discount_percent is not None and worst_pct > m.max_discount_percent:
        return True
    if m.approval_limit is not None:
        return compute_document_totals(document).grand_total > m.approval_limit
    return False


def submit_quotation(document: SalesDocument, *, user) -> str:
    """DRAFT/PENDING → READY, or → PENDING_APPROVAL when the discount exceeds ``user``'s cap.
    Returns the resulting status."""
    if document.status not in (DocStatus.DRAFT, DocStatus.PENDING_APPROVAL):
        raise WorkflowError(
            f"ส่งขออนุมัติ/เตรียมส่งได้เฉพาะเอกสารร่าง (สถานะปัจจุบัน: {document.get_status_display()})"
        )
    document.status = (
        DocStatus.PENDING_APPROVAL if discount_exceeds_cap(document, user=user) else DocStatus.READY
    )
    document.save()
    return document.status


def approve_quotation(document: SalesDocument, *, user) -> None:
    """PENDING_APPROVAL → READY, stamping who approved. Caller must check ``can_approve``."""
    if document.status != DocStatus.PENDING_APPROVAL:
        raise WorkflowError("อนุมัติได้เฉพาะเอกสารที่รออนุมัติ")
    document.status = DocStatus.READY
    document.approved_by = user if getattr(user, "is_authenticated", False) else None
    document.approved_at = timezone.now()
    document.save()


def reject_approval(document: SalesDocument, *, user=None, note: str = "") -> None:
    """PENDING_APPROVAL → DRAFT (the salesperson revises and resubmits)."""
    if document.status != DocStatus.PENDING_APPROVAL:
        raise WorkflowError("ตีกลับได้เฉพาะเอกสารที่รออนุมัติ")
    document.status = DocStatus.DRAFT
    document.save()


def cancel_quotation(document: SalesDocument) -> None:
    """Cancel a quotation (any non-cancelled state → CANCELLED). Idempotent."""
    if document.status == DocStatus.CANCELLED:
        return
    document.status = DocStatus.CANCELLED
    document.save()


def reopen_quotation(document: SalesDocument, *, reason: str = "") -> SalesDocument:
    """Reopen a sent/accepted/rejected/expired quotation for changes: bump the revision counter,
    back to DRAFT, clear the customer response & approval stamp. ``reason`` is remembered on the
    document and ends up on the next revision snapshot (taken when it's re-sent). The version that
    was sent is already frozen in a ``QuotationRevision``, so reopening doesn't lose it."""
    if document.status not in document.REOPENABLE_STATUSES:
        raise WorkflowError(f"เอกสารในสถานะ “{document.get_status_display()}” เปิดแก้ไขใหม่ไม่ได้")
    document.revision += 1
    document.revision_note = reason
    document.status = DocStatus.DRAFT
    document.sent_at = None
    document.customer_response = ""
    document.customer_signed_name = ""
    document.customer_response_note = ""
    document.customer_responded_at = None
    document.customer_response_ip = None
    document.approved_by = None
    document.approved_at = None
    document.save()
    return document


def expire_overdue_quotations() -> int:
    """Move every READY/SENT quotation in the current tenant whose ``valid_until`` has passed to
    EXPIRED. Returns how many changed. (Run from the ``expire_quotations`` management command.)"""
    qs = SalesDocument.objects.filter(
        doc_type=DocType.QUOTATION,
        status__in=[DocStatus.READY, DocStatus.SENT],
        valid_until__lt=date.today(),
    )
    count = 0
    for doc in qs:
        doc.status = DocStatus.EXPIRED
        doc.save()
        count += 1
    return count


# --- Totals engine ------------------------------------------------------------
@dataclass
class GroupTotal:
    label: str
    lines: list
    subtotal: Decimal


@dataclass
class DocumentTotals:
    groups: list  # of GroupTotal
    inclusive: bool  # True if line prices already include VAT
    subtotal: Decimal  # sum of line amounts (gross if inclusive, net if exclusive)
    end_discount: Decimal
    after_discount: Decimal
    base_vat7: Decimal  # the ex-VAT base that 7% applies to
    base_vat0: Decimal
    base_exempt: Decimal
    base_none: Decimal
    vat_amount: Decimal
    rounding: Decimal  # reconciliation residual shown as a "ปัดเศษ" line if non-zero
    grand_total: Decimal
    withholding_estimate: Decimal
    net_expected: Decimal
    amount_in_words: str
    has_zero_rated: bool


_ONE_PLUS_VAT = Decimal(1) + VAT_RATE


def compute_document_totals(document: SalesDocument) -> DocumentTotals:
    """Subtotal → end-of-bill discount (allocated proportionally) → VAT bases per rate → VAT →
    grand total + withholding estimate + BahtText. Supports both exclusive and inclusive pricing
    (``document.price_mode``): in inclusive mode the line amounts already contain VAT, so the 7%
    base is backed out (``amount / 1.07``) and the grand total equals the gross after discount."""
    inclusive = document.price_mode == PriceMode.INCLUSIVE
    lines = list(document.lines.all())
    item_lines = [ln for ln in lines if ln.line_type == LineType.ITEM]
    amounts: dict[int, Decimal] = {ln.pk: ln.amount for ln in item_lines}
    subtotal = sum(amounts.values(), Decimal(0))

    if document.end_discount_kind == DiscountKind.PERCENT:
        end_discount = subtotal * Decimal(document.end_discount_value) / 100
    else:
        end_discount = Decimal(document.end_discount_value)
    end_discount = min(end_discount, subtotal) if subtotal > 0 else Decimal(0)
    after_discount = subtotal - end_discount

    bases: dict[str, Decimal] = {
        t: Decimal(0) for t in (TaxType.VAT7, TaxType.VAT0, TaxType.EXEMPT, TaxType.NONE)
    }
    vat_amount = Decimal(0)
    withholding = Decimal(0)
    for ln in item_lines:
        amt = amounts[ln.pk]
        alloc = (amt / subtotal * end_discount) if subtotal > 0 else Decimal(0)
        post = amt - alloc  # this line's value after its share of the end-of-bill discount
        if ln.tax_type == TaxType.VAT7:
            base = post / _ONE_PLUS_VAT if inclusive else post
            vat_amount += (post - base) if inclusive else post * VAT_RATE
        else:
            base = post
        bases[ln.tax_type] = bases.get(ln.tax_type, Decimal(0)) + base
        withholding += base * Decimal(ln.withholding_rate) / 100

    base_vat7 = _q2(bases[TaxType.VAT7])
    base_vat0 = _q2(bases[TaxType.VAT0])
    base_exempt = _q2(bases[TaxType.EXEMPT])
    base_none = _q2(bases[TaxType.NONE])
    vat_amount_d = _q2(vat_amount)
    grand_total = _q2(after_discount if inclusive else after_discount + vat_amount)
    rounding = grand_total - (base_vat7 + base_vat0 + base_exempt + base_none + vat_amount_d)
    withholding_d = _q2(withholding)
    net_expected = grand_total - withholding_d

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
                        amounts.get(ln.pk, Decimal(0))
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
        inclusive=inclusive,
        subtotal=_q2(subtotal),
        end_discount=_q2(end_discount),
        after_discount=_q2(after_discount),
        base_vat7=base_vat7,
        base_vat0=base_vat0,
        base_exempt=base_exempt,
        base_none=base_none,
        vat_amount=vat_amount_d,
        rounding=rounding,
        grand_total=grand_total,
        withholding_estimate=withholding_d,
        net_expected=_q2(net_expected),
        amount_in_words=baht_text(grand_total),
        has_zero_rated=bool(base_vat0 or base_exempt or base_none),
    )
