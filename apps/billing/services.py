"""Billing services — conversions along the sales-document chain, payment recording, AR & sales-tax
reports. Logic lives here, not in views (CLAUDE.md §8). Reuses ``apps.quotes.services`` for the
totals engine and the locked-row document-number allocator.

Invariants: money is ``Decimal`` (CLAUDE.md §4.2); tax-document numbers are gap-free and assigned
only at *issue* time inside a transaction (§4.3); issued tax docs are immutable (§4.4); rates are
snapshotted onto the cloned lines (§4.6).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.quotes.models import DocStatus, DocType, LineType, SalesDocLine, SalesDocument
from apps.quotes.services import (
    WorkflowError,
    compute_document_totals,
    next_document_number,
)

_Q2 = Decimal("0.01")


def _q2(value) -> Decimal:
    return Decimal(value).quantize(_Q2, rounding=ROUND_HALF_UP)


def _clone_lines(src: SalesDocument, dst: SalesDocument) -> None:
    for ln in src.lines.all():
        SalesDocLine.objects.create(
            document=dst,
            group_label=ln.group_label,
            position=ln.position,
            line_type=ln.line_type,
            product=ln.product,
            variant=ln.variant,
            description=ln.description,
            dimensions=ln.dimensions,
            material=ln.material,
            quantity=ln.quantity,
            unit=ln.unit,
            unit_price=ln.unit_price,
            discount_kind=ln.discount_kind,
            discount_value=ln.discount_value,
            tax_type=ln.tax_type,
            withholding_rate=ln.withholding_rate,
        )


def _copy_header(src: SalesDocument, dst: SalesDocument) -> None:
    dst.deal = src.deal
    dst.customer = src.customer
    dst.contact = src.contact
    dst.salesperson = src.salesperson
    dst.currency = src.currency
    dst.price_mode = src.price_mode
    dst.end_discount_kind = src.end_discount_kind
    dst.end_discount_value = src.end_discount_value
    dst.payment_terms = src.payment_terms
    dst.lead_time = src.lead_time
    dst.warranty = src.warranty
    dst.notes = src.notes
    dst.bank_account = src.bank_account
    dst.reference = src.reference


@transaction.atomic
def create_invoice_from_quotation(quote: SalesDocument, *, user=None) -> SalesDocument:
    """Clone an accepted quotation into a DRAFT INVOICE (snapshotting all line rates). Invoices are
    not tax documents, so they get a number from the start (a fresh ``INV-`` number). Re-running it
    for the same quotation just creates another invoice — the caller should guard against that."""
    if quote.doc_type != DocType.QUOTATION:
        raise WorkflowError("แปลงเป็นใบแจ้งหนี้ได้จากใบเสนอราคาเท่านั้น")
    today = date.today()
    credit_days = (quote.customer.default_credit_days if quote.customer else 0) or 0
    inv = SalesDocument(
        doc_type=DocType.INVOICE,
        status=DocStatus.DRAFT,
        issue_date=today,
        due_date=today + timedelta(days=credit_days),
        source_document=quote,
    )
    _copy_header(quote, inv)
    inv.save()
    inv.doc_number = next_document_number(DocType.INVOICE, prefix="INV")
    inv.save(update_fields=["doc_number"])
    _clone_lines(quote, inv)
    return inv


@transaction.atomic
def issue_tax_invoice(invoice: SalesDocument, *, user=None) -> SalesDocument:
    """Issue a full-form tax invoice (Revenue Code §86/4) from an invoice. **Assigns the gap-free
    TAX number inside this transaction** and stamps ``issued_at`` — this is the immutability point."""
    if invoice.doc_type != DocType.INVOICE:
        raise WorkflowError("ออกใบกำกับภาษีได้จากใบแจ้งหนี้เท่านั้น")
    existing = SalesDocument.objects.filter(
        source_document=invoice, doc_type=DocType.TAX_INVOICE
    ).exclude(status=DocStatus.CANCELLED)
    if existing.exists():
        raise WorkflowError("ใบแจ้งหนี้นี้ออกใบกำกับภาษีไปแล้ว")
    tax = SalesDocument(
        doc_type=DocType.TAX_INVOICE,
        status=DocStatus.SENT,
        issue_date=date.today(),
        source_document=invoice,
    )
    _copy_header(invoice, tax)
    tax.save()
    _clone_lines(invoice, tax)
    tax.doc_number = next_document_number(DocType.TAX_INVOICE, prefix="TAX")
    tax.issued_at = timezone.now()
    tax.save()  # DB still has doc_number="" at this point, so the immutability guard allows it
    return tax


@transaction.atomic
def create_receipt_from_payment(payment, *, user=None) -> SalesDocument:
    """A RECEIPT (ใบเสร็จรับเงิน) summarising a payment — one line per allocated invoice (or a single
    summary line), gap-free RCP number, ``issued_at`` stamped, and linked back from the payment."""
    if payment.receipt_document_id:
        return payment.receipt_document
    rcp = SalesDocument(
        doc_type=DocType.RECEIPT,
        status=DocStatus.SENT,
        issue_date=payment.date,
        customer=payment.customer,
        salesperson=payment.recorded_by,
        bank_account=payment.bank_account,
        reference=payment.reference,
        price_mode="incl",  # receipt amounts are gross cash received
    )
    rcp.save()
    allocs = list(payment.allocations.select_related("invoice"))
    pos = 0
    if allocs:
        for a in allocs:
            pos += 1
            SalesDocLine.objects.create(
                document=rcp,
                position=pos,
                line_type=LineType.ITEM,
                description=f"รับชำระตามใบแจ้งหนี้ {a.invoice.doc_number or a.invoice.pk}",
                quantity=1,
                unit="รายการ",
                unit_price=a.amount,
                tax_type="none",
            )
    else:
        SalesDocLine.objects.create(
            document=rcp,
            position=1,
            line_type=LineType.ITEM,
            description="รับชำระเงิน",
            quantity=1,
            unit="รายการ",
            unit_price=payment.gross_amount,
            tax_type="none",
        )
    rcp.doc_number = next_document_number(DocType.RECEIPT, prefix="RCP")
    rcp.issued_at = timezone.now()
    rcp.save()
    payment.receipt_document = rcp
    payment.save(update_fields=["receipt_document"])
    return rcp


def invoice_outstanding(invoice: SalesDocument) -> Decimal:
    """Grand total − allocated payments − credit-note adjustments referencing this invoice's tax
    invoice. Returns 0 if the invoice is cancelled."""
    if invoice.status == DocStatus.CANCELLED:
        return Decimal("0.00")
    total = compute_document_totals(invoice).grand_total
    from .models import PaymentAllocation

    paid = sum((a.amount for a in PaymentAllocation.objects.filter(invoice=invoice)), Decimal(0))
    # credit notes against the tax invoice derived from this invoice
    credited = Decimal(0)
    tax = SalesDocument.objects.filter(
        source_document=invoice, doc_type=DocType.TAX_INVOICE
    ).first()
    if tax is not None:
        for cn in SalesDocument.objects.filter(
            references_document=tax, doc_type=DocType.CREDIT_NOTE
        ).exclude(status=DocStatus.CANCELLED):
            credited += compute_document_totals(cn).grand_total
    return _q2(total - paid - credited)


@transaction.atomic
def record_payment(
    *,
    customer,
    date,  # noqa: A002 - matches REQUIREMENTS naming
    method,
    gross_amount,
    allocations: list[tuple[SalesDocument, Decimal]],
    bank_account=None,
    fee=Decimal(0),
    withholding_deducted=Decimal(0),
    withholding_cert_ref: str = "",
    reference: str = "",
    notes: str = "",
    user=None,
    issue_receipt: bool = False,
):
    """Create a ``Payment`` + its ``PaymentAllocation`` rows, validating no allocation exceeds the
    invoice's outstanding amount. Optionally issues a Receipt for the payment."""
    from .models import Payment, PaymentAllocation

    payment = Payment.objects.create(
        customer=customer,
        date=date,
        method=method,
        bank_account=bank_account,
        gross_amount=Decimal(gross_amount),
        fee=Decimal(fee or 0),
        withholding_deducted=Decimal(withholding_deducted or 0),
        withholding_cert_ref=withholding_cert_ref,
        reference=reference,
        notes=notes,
        recorded_by=user if getattr(user, "is_authenticated", False) else None,
    )
    for invoice, amount in allocations:
        amount = Decimal(amount)
        if amount <= 0:
            continue
        if invoice.doc_type != DocType.INVOICE:
            raise WorkflowError("ตัดชำระได้กับใบแจ้งหนี้เท่านั้น")
        if amount > invoice_outstanding(invoice) + Decimal("0.005"):
            raise WorkflowError(
                f"ยอดตัดชำระ {amount} เกินยอดค้างของใบแจ้งหนี้ {invoice.doc_number or invoice.pk}"
            )
        PaymentAllocation.objects.create(payment=payment, invoice=invoice, amount=amount)
    if issue_receipt:
        create_receipt_from_payment(payment, user=user)
    return payment


@transaction.atomic
def create_credit_note(
    tax_invoice: SalesDocument, *, reason: str, lines=None, user=None
) -> SalesDocument:
    """A CREDIT_NOTE (ใบลดหนี้, §86/9) referencing a tax invoice. ``lines`` is an optional list of
    ``{description, quantity, unit_price, tax_type?}`` — if omitted, a single negative summary line
    equal to the tax invoice's grand total is created (full reversal)."""
    if tax_invoice.doc_type != DocType.TAX_INVOICE:
        raise WorkflowError("ออกใบลดหนี้ได้จากใบกำกับภาษีเท่านั้น")
    if not reason.strip():
        raise WorkflowError("ต้องระบุเหตุผลของการลดหนี้")
    cn = SalesDocument(
        doc_type=DocType.CREDIT_NOTE,
        status=DocStatus.SENT,
        issue_date=date.today(),
        references_document=tax_invoice,
        source_document=tax_invoice,
        notes=reason,
    )
    _copy_header(tax_invoice, cn)
    cn.save()
    pos = 0
    if lines:
        for item in lines:
            pos += 1
            SalesDocLine.objects.create(
                document=cn,
                position=pos,
                line_type=LineType.ITEM,
                description=item["description"],
                quantity=Decimal(str(item.get("quantity", 1))),
                unit=item.get("unit", "รายการ"),
                unit_price=Decimal(str(item["unit_price"])),
                tax_type=item.get("tax_type", "vat7"),
            )
    else:
        # full reversal — mirror the tax invoice's lines as negatives
        for ln in tax_invoice.lines.all():
            if ln.line_type != LineType.ITEM:
                continue
            pos += 1
            SalesDocLine.objects.create(
                document=cn,
                group_label=ln.group_label,
                position=pos,
                line_type=LineType.ITEM,
                description=ln.description,
                dimensions=ln.dimensions,
                material=ln.material,
                quantity=ln.quantity,
                unit=ln.unit,
                unit_price=-ln.unit_price,
                tax_type=ln.tax_type,
            )
    cn.doc_number = next_document_number(DocType.CREDIT_NOTE, prefix="CN")
    cn.issued_at = timezone.now()
    cn.save()
    return cn


@transaction.atomic
def cancel_tax_document(doc: SalesDocument, *, reason: str, user=None) -> None:
    """Cancel an issued tax document — keeps ``doc_number``, sets ``status=CANCELLED`` and the
    reason (CLAUDE.md §4.3). Refuses if the doc has non-cancelled dependents (e.g. a tax invoice
    that already has a receipt or credit note)."""
    if doc.status == DocStatus.CANCELLED:
        return
    if not reason.strip():
        raise WorkflowError("ต้องระบุเหตุผลของการยกเลิก")
    deps = SalesDocument.objects.filter(references_document=doc).exclude(status=DocStatus.CANCELLED)
    if deps.exists():
        raise WorkflowError("ยกเลิกไม่ได้ — มีเอกสารอื่นอ้างอิงเอกสารนี้อยู่ (เช่น ใบลดหนี้)")
    doc.status = DocStatus.CANCELLED
    doc.cancelled_reason = reason
    doc.save(update_fields=["status", "cancelled_reason", "updated_at"])


# --- Reports ------------------------------------------------------------------
_AGING_BUCKETS = ("not_due", "1_30", "31_60", "61_90", "over_90")


def _bucket_for(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "not_due"
    if days_overdue <= 30:
        return "1_30"
    if days_overdue <= 60:
        return "31_60"
    if days_overdue <= 90:
        return "61_90"
    return "over_90"


def ar_aging(*, as_of: date | None = None) -> dict:
    """AR aging for the current tenant: per-customer + overall outstanding by bucket."""
    as_of = as_of or date.today()
    invoices = (
        SalesDocument.objects.filter(doc_type=DocType.INVOICE)
        .exclude(status=DocStatus.CANCELLED)
        .select_related("customer")
        .prefetch_related("lines")
    )
    by_customer: dict = {}
    totals = {b: Decimal("0.00") for b in _AGING_BUCKETS}
    totals["total"] = Decimal("0.00")
    for inv in invoices:
        out = invoice_outstanding(inv)
        if out <= 0:
            continue
        due = inv.due_date or inv.issue_date
        bucket = _bucket_for((as_of - due).days)
        cid = inv.customer_id
        row = by_customer.setdefault(
            cid,
            {
                "customer": inv.customer.name if inv.customer else "—",
                **{b: Decimal("0.00") for b in _AGING_BUCKETS},
                "total": Decimal("0.00"),
            },
        )
        row[bucket] += out
        row["total"] += out
        totals[bucket] += out
        totals["total"] += out
    return {
        "as_of": as_of,
        "buckets": list(_AGING_BUCKETS),
        "rows": sorted(by_customer.values(), key=lambda r: r["customer"]),
        "totals": totals,
    }


def sales_tax_report(*, year: int, month: int) -> dict:
    """ภ.พ.30 / sales-tax report for a tax month: each issued TAX_INVOICE / CREDIT_NOTE / DEBIT_NOTE
    with {doc_no, date, buyer_name, buyer_tax_id, value (ex-VAT base), vat_amount, cancelled?} + totals.
    Note: ``year``/``month`` are Gregorian (the document ``issue_date``)."""
    docs = (
        SalesDocument.objects.filter(
            doc_type__in=[DocType.TAX_INVOICE, DocType.CREDIT_NOTE, DocType.DEBIT_NOTE],
            issue_date__year=year,
            issue_date__month=month,
        )
        .exclude(doc_number="")
        .select_related("customer")
        .prefetch_related("lines")
        .order_by("issue_date", "doc_number")
    )
    rows = []
    total_base = Decimal("0.00")
    total_vat = Decimal("0.00")
    for d in docs:
        t = compute_document_totals(d)
        cancelled = d.status == DocStatus.CANCELLED
        base = t.base_vat7 + t.base_vat0 + t.base_exempt + t.base_none
        vat = t.vat_amount
        sign = Decimal(-1) if d.doc_type == DocType.CREDIT_NOTE else Decimal(1)
        rows.append(
            {
                "doc_no": d.doc_number,
                "doc_type": d.get_doc_type_display(),
                "date": d.issue_date,
                "buyer_name": d.customer.name if d.customer else "",
                "buyer_tax_id": d.customer.tax_id if d.customer else "",
                "value": base,
                "vat_amount": vat,
                "cancelled": cancelled,
            }
        )
        if not cancelled:
            total_base += sign * base
            total_vat += sign * vat
    return {
        "year": year,
        "month": month,
        "rows": rows,
        "total_base": _q2(total_base),
        "total_vat": _q2(total_vat),
    }
