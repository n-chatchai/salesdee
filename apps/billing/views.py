"""Billing views — invoices, tax invoices, receipts, payments, credit notes, AR aging & sales-tax
report. Thin views: logic is in ``services.py``. Write actions are gated to owner/manager/accounting
(``_can_write``); reads to anyone who can view reports + sales (configurable — kept simple here)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.crm.models import Customer
from apps.quotes.models import DocStatus, DocType, SalesDocument
from apps.quotes.services import WorkflowError, compute_document_totals

from . import services
from .models import Payment, PaymentMethod
from .pdf import (
    render_credit_note_pdf,
    render_debit_note_pdf,
    render_receipt_pdf,
    render_tax_invoice_pdf,
)


def _membership(request):
    from apps.core.permissions import membership_of

    return membership_of(request)


def _can_write(request) -> bool:
    from apps.accounts.models import Role

    m = _membership(request)
    return m is not None and m.role in (Role.OWNER, Role.MANAGER, Role.ACCOUNTING)


def _require_write(request) -> None:
    if not _can_write(request):
        raise PermissionDenied("คุณไม่มีสิทธิ์ใช้งานเมนูบัญชี/การเงิน")


def _docs(doc_type: str):
    return SalesDocument.objects.filter(doc_type=doc_type)


# --- Invoices -----------------------------------------------------------------
@login_required
def invoices(request: HttpRequest) -> HttpResponse:
    rows = []
    for inv in _docs(DocType.INVOICE).select_related("customer").prefetch_related("lines"):
        rows.append((inv, compute_document_totals(inv), services.invoice_outstanding(inv)))
    return render(
        request,
        "billing/_list.html",
        {
            "rows": rows,
            "title": "ใบแจ้งหนี้ / ใบวางบิล",
            "detail_url": "billing:invoice_detail",
            "show_outstanding": True,
            "can_create_payment": _can_write(request),
        },
    )


@login_required
def invoice_detail(request: HttpRequest, pk: int) -> HttpResponse:
    inv = get_object_or_404(_docs(DocType.INVOICE).prefetch_related("lines"), pk=pk)
    tax = SalesDocument.objects.filter(source_document=inv, doc_type=DocType.TAX_INVOICE).first()
    return render(
        request,
        "billing/invoice_detail.html",
        {
            "document": inv,
            "title": "ใบแจ้งหนี้",
            "totals": compute_document_totals(inv),
            "outstanding": services.invoice_outstanding(inv),
            "tax_invoice": tax,
            "can_write": _can_write(request),
            "editable": False,
        },
    )


@login_required
@require_POST
def quotation_to_invoice(request: HttpRequest, quote_pk: int) -> HttpResponse:
    _require_write(request)
    quote = get_object_or_404(SalesDocument, pk=quote_pk, doc_type=DocType.QUOTATION)
    if quote.status not in (DocStatus.ACCEPTED, DocStatus.SENT):
        messages.warning(request, "ควรแปลงเป็นใบแจ้งหนี้เมื่อใบเสนอราคาได้รับการตอบรับแล้ว")
    inv = services.create_invoice_from_quotation(quote, user=request.user)
    messages.success(request, f"สร้างใบแจ้งหนี้ {inv.doc_number} แล้ว")
    return redirect("billing:invoice_detail", pk=inv.pk)


@login_required
@require_POST
def invoice_issue_tax(request: HttpRequest, pk: int) -> HttpResponse:
    from apps.tenants.quota import QuotaExceeded

    _require_write(request)
    inv = get_object_or_404(_docs(DocType.INVOICE), pk=pk)
    try:
        tax = services.issue_tax_invoice(inv, user=request.user)
    except QuotaExceeded as e:
        messages.error(request, str(e))
        return redirect("billing:invoice_detail", pk=inv.pk)
    except WorkflowError as e:
        messages.error(request, str(e))
        return redirect("billing:invoice_detail", pk=inv.pk)
    messages.success(request, f"ออกใบกำกับภาษี {tax.doc_number} แล้ว")
    return redirect("billing:tax_invoice_detail", pk=tax.pk)


@login_required
@require_POST
def invoice_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    _require_write(request)
    inv = get_object_or_404(_docs(DocType.INVOICE), pk=pk)
    inv.status = DocStatus.CANCELLED
    inv.cancelled_reason = request.POST.get("reason", "")
    inv.save()
    messages.success(request, "ยกเลิกใบแจ้งหนี้แล้ว")
    return redirect("billing:invoice_detail", pk=inv.pk)


# --- Tax invoices -------------------------------------------------------------
@login_required
def tax_invoices(request: HttpRequest) -> HttpResponse:
    rows = [
        (d, compute_document_totals(d))
        for d in _docs(DocType.TAX_INVOICE).select_related("customer").prefetch_related("lines")
    ]
    return render(
        request,
        "billing/_list.html",
        {"rows": rows, "title": "ใบกำกับภาษี", "detail_url": "billing:tax_invoice_detail"},
    )


@login_required
def tax_invoice_detail(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(_docs(DocType.TAX_INVOICE).prefetch_related("lines"), pk=pk)
    return render(
        request,
        "billing/tax_invoice_detail.html",
        {
            "document": doc,
            "title": "ใบกำกับภาษี",
            "totals": compute_document_totals(doc),
            "credit_notes": SalesDocument.objects.filter(
                references_document=doc, doc_type=DocType.CREDIT_NOTE
            ),
            "debit_notes": SalesDocument.objects.filter(
                references_document=doc, doc_type=DocType.DEBIT_NOTE
            ),
            "can_write": _can_write(request),
            "editable": False,
        },
    )


def _pdf_response(data: bytes, filename: str) -> HttpResponse:
    resp = HttpResponse(data, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{filename}.pdf"'
    return resp


@login_required
def tax_invoice_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(_docs(DocType.TAX_INVOICE), pk=pk)
    copy = request.GET.get("copy") == "1"
    return _pdf_response(render_tax_invoice_pdf(doc, copy=copy), doc.doc_number or f"tax-{doc.pk}")


# --- Receipts -----------------------------------------------------------------
@login_required
def receipts(request: HttpRequest) -> HttpResponse:
    rows = [
        (d, compute_document_totals(d))
        for d in _docs(DocType.RECEIPT).select_related("customer").prefetch_related("lines")
    ]
    return render(
        request,
        "billing/_list.html",
        {"rows": rows, "title": "ใบเสร็จรับเงิน", "detail_url": "billing:receipt_detail"},
    )


@login_required
def receipt_detail(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(_docs(DocType.RECEIPT).prefetch_related("lines"), pk=pk)
    return render(
        request,
        "billing/receipt_detail.html",
        {
            "document": doc,
            "title": "ใบเสร็จรับเงิน",
            "totals": compute_document_totals(doc),
            "editable": False,
        },
    )


@login_required
def receipt_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(_docs(DocType.RECEIPT), pk=pk)
    return _pdf_response(render_receipt_pdf(doc), doc.doc_number or f"rcp-{doc.pk}")


# --- Credit notes -------------------------------------------------------------
@login_required
def credit_notes(request: HttpRequest) -> HttpResponse:
    rows = [
        (d, compute_document_totals(d))
        for d in _docs(DocType.CREDIT_NOTE).select_related("customer").prefetch_related("lines")
    ]
    return render(
        request,
        "billing/_list.html",
        {"rows": rows, "title": "ใบลดหนี้", "detail_url": "billing:credit_note_detail"},
    )


@login_required
def credit_note_detail(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(_docs(DocType.CREDIT_NOTE).prefetch_related("lines"), pk=pk)
    return render(
        request,
        "billing/credit_note_detail.html",
        {
            "document": doc,
            "title": "ใบลดหนี้",
            "totals": compute_document_totals(doc),
            "editable": False,
        },
    )


@login_required
def credit_note_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(_docs(DocType.CREDIT_NOTE), pk=pk)
    return _pdf_response(render_credit_note_pdf(doc), doc.doc_number or f"cn-{doc.pk}")


@login_required
def credit_note_create(request: HttpRequest, tax_pk: int) -> HttpResponse:
    _require_write(request)
    tax = get_object_or_404(_docs(DocType.TAX_INVOICE), pk=tax_pk)
    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        try:
            cn = services.create_credit_note(tax, reason=reason, user=request.user)
        except WorkflowError as e:
            messages.error(request, str(e))
            return redirect("billing:tax_invoice_detail", pk=tax.pk)
        messages.success(request, f"ออกใบลดหนี้ {cn.doc_number} (ลดเต็มจำนวน)")
        return redirect("billing:credit_note_detail", pk=cn.pk)
    return render(request, "billing/credit_note_create.html", {"tax_invoice": tax})


# --- Debit notes -------------------------------------------------------------
@login_required
def debit_notes(request: HttpRequest) -> HttpResponse:
    rows = [
        (d, compute_document_totals(d))
        for d in _docs(DocType.DEBIT_NOTE).select_related("customer").prefetch_related("lines")
    ]
    return render(
        request,
        "billing/_list.html",
        {"rows": rows, "title": "ใบเพิ่มหนี้", "detail_url": "billing:debit_note_detail"},
    )


@login_required
def debit_note_detail(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(_docs(DocType.DEBIT_NOTE).prefetch_related("lines"), pk=pk)
    return render(
        request,
        "billing/debit_note_detail.html",
        {
            "document": doc,
            "title": "ใบเพิ่มหนี้",
            "totals": compute_document_totals(doc),
            "editable": False,
        },
    )


@login_required
def debit_note_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(_docs(DocType.DEBIT_NOTE), pk=pk)
    return _pdf_response(render_debit_note_pdf(doc), doc.doc_number or f"dn-{doc.pk}")


@login_required
def debit_note_create(request: HttpRequest, tax_pk: int) -> HttpResponse:
    _require_write(request)
    tax = get_object_or_404(_docs(DocType.TAX_INVOICE), pk=tax_pk)
    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        try:
            dn = services.create_debit_note(tax, reason=reason, user=request.user)
        except WorkflowError as e:
            messages.error(request, str(e))
            return redirect("billing:tax_invoice_detail", pk=tax.pk)
        messages.success(request, f"ออกใบเพิ่มหนี้ {dn.doc_number}")
        return redirect("billing:debit_note_detail", pk=dn.pk)
    return render(request, "billing/debit_note_create.html", {"tax_invoice": tax})


_DOC_TYPE_BY_KIND = {
    "tax_invoice": DocType.TAX_INVOICE,
    "receipt": DocType.RECEIPT,
    "credit_note": DocType.CREDIT_NOTE,
    "debit_note": DocType.DEBIT_NOTE,
}

_DOC_KIND_REDIRECT = {
    "tax_invoice": "billing:tax_invoice_detail",
    "receipt": "billing:receipt_detail",
    "credit_note": "billing:credit_note_detail",
    "debit_note": "billing:debit_note_detail",
}

_DOC_KIND_PDF_URL = {
    "tax_invoice": "billing:tax_invoice_pdf",
    "receipt": "billing:receipt_pdf",
    "credit_note": "billing:credit_note_pdf",
    "debit_note": "billing:debit_note_pdf",
}


def _doc_for_send(request: HttpRequest, kind: str, pk: int):
    if kind not in _DOC_TYPE_BY_KIND:
        raise Http404("ชนิดเอกสารไม่รองรับ")
    return get_object_or_404(_docs(_DOC_TYPE_BY_KIND[kind]).select_related("customer"), pk=pk)


@login_required
@require_POST
def billing_doc_send_email(request: HttpRequest, kind: str, pk: int) -> HttpResponse:
    from .tasks import send_billing_doc_email

    doc = _doc_for_send(request, kind, pk)
    contact = doc.customer.contacts.exclude(email="").first() if doc.customer else None
    if contact is None:
        messages.error(request, "ยังไม่มีอีเมลของผู้ติดต่อสำหรับลูกค้ารายนี้")
        return redirect(_DOC_KIND_REDIRECT[kind], pk=doc.pk)
    send_billing_doc_email.enqueue(doc.pk, doc.tenant_id, recipient_email=contact.email, kind=kind)
    from apps.audit.services import record as audit_record

    audit_record(
        request.user,
        action=f"{kind}.sent",
        obj=doc,
        object_repr=doc.doc_number or str(doc),
        changes={"channel": "email", "to": contact.email},
        ip=request.META.get("REMOTE_ADDR"),
    )
    messages.success(request, f"กำลังส่ง{doc.get_doc_type_display()} ทางอีเมลถึง {contact.email} …")
    return redirect(_DOC_KIND_REDIRECT[kind], pk=doc.pk)


@login_required
@require_POST
def billing_doc_send_line(request: HttpRequest, kind: str, pk: int) -> HttpResponse:
    from apps.integrations.line import line_is_configured

    from .tasks import send_billing_doc_line

    doc = _doc_for_send(request, kind, pk)
    if not line_is_configured():
        messages.error(request, "ยังไม่ได้ตั้งค่าการเชื่อม LINE OA สำหรับ workspace นี้")
        return redirect(_DOC_KIND_REDIRECT[kind], pk=doc.pk)
    contact = doc.customer.contacts.exclude(line_id="").first() if doc.customer else None
    if contact is None:
        messages.error(request, "ยังไม่มี LINE ID ของผู้ติดต่อ")
        return redirect(_DOC_KIND_REDIRECT[kind], pk=doc.pk)
    from django.urls import reverse

    pdf_url = request.build_absolute_uri(reverse(_DOC_KIND_PDF_URL[kind], args=[doc.pk]))
    send_billing_doc_line.enqueue(
        doc.pk, doc.tenant_id, recipient=contact.line_id, kind=kind, pdf_url=pdf_url
    )
    from apps.audit.services import record as audit_record

    audit_record(
        request.user,
        action=f"{kind}.sent",
        obj=doc,
        object_repr=doc.doc_number or str(doc),
        changes={"channel": "line", "to": contact.line_id},
        ip=request.META.get("REMOTE_ADDR"),
    )
    messages.success(request, f"กำลังส่ง{doc.get_doc_type_display()} ทาง LINE …")
    return redirect(_DOC_KIND_REDIRECT[kind], pk=doc.pk)


@login_required
@require_POST
def tax_invoice_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    _require_write(request)
    doc = get_object_or_404(_docs(DocType.TAX_INVOICE), pk=pk)
    try:
        services.cancel_tax_document(doc, reason=request.POST.get("reason", "ยกเลิกตามคำขอ"))
    except WorkflowError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "ยกเลิกใบกำกับภาษีแล้ว (เลขที่เดิมถูกเก็บไว้)")
    return redirect("billing:tax_invoice_detail", pk=doc.pk)


# --- Payments -----------------------------------------------------------------
@login_required
def payments(request: HttpRequest) -> HttpResponse:
    rows = Payment.objects.select_related("customer").all()
    return render(request, "billing/payments.html", {"rows": rows})


@login_required
def payment_detail(request: HttpRequest, pk: int) -> HttpResponse:
    payment = get_object_or_404(
        Payment.objects.select_related("customer").prefetch_related("allocations__invoice"), pk=pk
    )
    return render(request, "billing/payment_detail.html", {"payment": payment})


@login_required
def payment_create(request: HttpRequest) -> HttpResponse:
    _require_write(request)
    customers = Customer.objects.filter(is_archived=False).order_by("name")
    customer_id = request.GET.get("customer") or request.POST.get("customer")
    open_invoices = []
    customer = None
    if customer_id:
        customer = Customer.objects.filter(pk=customer_id).first()
        if customer is not None:
            for inv in (
                _docs(DocType.INVOICE)
                .filter(customer=customer)
                .exclude(status=DocStatus.CANCELLED)
                .prefetch_related("lines")
            ):
                out = services.invoice_outstanding(inv)
                if out > 0:
                    open_invoices.append((inv, out))
    if request.method == "POST" and customer is not None:
        allocations = []
        for inv, _out in open_invoices:
            raw = request.POST.get(f"alloc_{inv.pk}", "").strip()
            if raw:
                try:
                    amt = Decimal(raw)
                except (ArithmeticError, ValueError):
                    amt = Decimal(0)
                if amt > 0:
                    allocations.append((inv, amt))
        try:
            payment = services.record_payment(
                customer=customer,
                date=request.POST.get("date") or date.today(),
                method=request.POST.get("method") or PaymentMethod.TRANSFER,
                gross_amount=Decimal(request.POST.get("gross_amount") or "0"),
                allocations=allocations,
                fee=Decimal(request.POST.get("fee") or "0"),
                withholding_deducted=Decimal(request.POST.get("withholding_deducted") or "0"),
                withholding_cert_ref=request.POST.get("withholding_cert_ref", ""),
                reference=request.POST.get("reference", ""),
                notes=request.POST.get("notes", ""),
                user=request.user,
                issue_receipt=request.POST.get("issue_receipt") == "1",
            )
        except (WorkflowError, ArithmeticError) as e:
            messages.error(request, str(e))
        else:
            messages.success(request, "บันทึกการรับชำระแล้ว")
            return redirect("billing:payment_detail", pk=payment.pk)
    return render(
        request,
        "billing/payment_create.html",
        {
            "customers": customers,
            "selected_customer": customer,
            "open_invoices": open_invoices,
            "methods": PaymentMethod.choices,
            "today": date.today(),
        },
    )


# --- Customer statements ------------------------------------------------------
@login_required
def customer_statement(request: HttpRequest, pk: int) -> HttpResponse:
    customer = get_object_or_404(Customer, pk=pk)
    data = services.customer_statement(customer)
    return render(request, "billing/customer_statement.html", {"data": data, "customer": customer})


@login_required
def customer_statement_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    customer = get_object_or_404(Customer, pk=pk)
    from .pdf import render_customer_statement_pdf

    data = services.customer_statement(customer)
    return _pdf_response(
        render_customer_statement_pdf(data, customer=customer),
        f"statement-{customer.pk}",
    )


@login_required
@require_POST
def customer_statement_send(request: HttpRequest, pk: int) -> HttpResponse:
    customer = get_object_or_404(Customer, pk=pk)
    from .tasks import send_customer_statement_email

    contact = customer.contacts.exclude(email="").first()
    if contact is None:
        messages.error(request, "ยังไม่มีอีเมลของผู้ติดต่อสำหรับลูกค้ารายนี้")
        return redirect("billing:customer_statement", pk=customer.pk)
    send_customer_statement_email.enqueue(
        customer.pk, customer.tenant_id, recipient_email=contact.email
    )
    from apps.audit.services import record as audit_record

    audit_record(
        request.user,
        action="customer_statement.sent",
        obj=customer,
        object_repr=customer.name,
        changes={"to": contact.email},
        ip=request.META.get("REMOTE_ADDR"),
    )
    messages.success(request, f"กำลังส่งใบแจ้งยอดให้ {contact.email} …")
    return redirect("billing:customer_statement", pk=customer.pk)


# --- Reports ------------------------------------------------------------------
@login_required
def ar_aging(request: HttpRequest) -> HttpResponse:
    data = services.ar_aging()
    return render(request, "billing/ar_aging.html", {"data": data})


@login_required
def sales_tax_report(request: HttpRequest) -> HttpResponse:
    today = date.today()
    year = int(request.GET.get("year") or today.year)
    month = int(request.GET.get("month") or today.month)
    data = services.sales_tax_report(year=year, month=month)
    if request.GET.get("export") == "xlsx":
        return _sales_tax_xlsx(data)
    return render(
        request,
        "billing/sales_tax_report.html",
        {"data": data, "year": year, "month": month, "months": range(1, 13)},
    )


def _sales_tax_xlsx(data: dict) -> HttpResponse:
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "รายงานภาษีขาย"
    ws.append(["เลขที่", "ชนิด", "วันที่", "ผู้ซื้อ", "เลขผู้เสียภาษี", "มูลค่า", "ภาษีมูลค่าเพิ่ม", "ยกเลิก"])
    for r in data["rows"]:
        ws.append(
            [
                r["doc_no"],
                r["doc_type"],
                r["date"].isoformat() if r["date"] else "",
                r["buyer_name"],
                r["buyer_tax_id"],
                float(r["value"]),
                float(r["vat_amount"]),
                "ยกเลิก" if r["cancelled"] else "",
            ]
        )
    ws.append([])
    ws.append(["", "", "", "", "รวม", float(data["total_base"]), float(data["total_vat"]), ""])
    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = (
        f'attachment; filename="sales-tax-{data["year"]}-{data["month"]:02d}.xlsx"'
    )
    return resp
