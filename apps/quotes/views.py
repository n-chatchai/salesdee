from __future__ import annotations

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Max
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.current_tenant import tenant_context
from apps.crm.models import Deal, Task, TaskKind

from .forms import QuotationForm, SalesDocLineForm
from .models import (
    CustomerResponse,
    DocStatus,
    DocType,
    QuotationShareLink,
    SalesDocLine,
    SalesDocument,
)
from .pdf import render_quotation_pdf
from .services import (
    apply_catalog_defaults,
    compute_document_totals,
    create_quotation_from_deal,
    get_or_create_share_link,
    mark_sent,
    next_document_number,
    record_customer_response,
)


@login_required
def quotation_list(request: HttpRequest) -> HttpResponse:
    docs = (
        SalesDocument.objects.filter(doc_type=DocType.QUOTATION)
        .select_related("customer", "salesperson")
        .prefetch_related("lines")
        .order_by("-created_at")
    )
    rows = [(d, compute_document_totals(d)) for d in docs]
    return render(request, "quotes/quotations.html", {"rows": rows})


@login_required
def quotation_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = QuotationForm(request.POST)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.doc_type = DocType.QUOTATION
            doc.status = DocStatus.DRAFT
            doc.doc_number = next_document_number(DocType.QUOTATION, prefix="QT")
            doc.save()
            return redirect("quotes:quotation_detail", pk=doc.pk)
    else:
        today = date.today()
        form = QuotationForm(
            initial={
                "issue_date": today,
                "valid_until": today + timedelta(days=30),
                "salesperson": request.user,
            }
        )
    return render(request, "quotes/quotation_form.html", {"form": form, "document": None})


@login_required
def quotation_edit(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(SalesDocument, pk=pk, doc_type=DocType.QUOTATION)
    if request.method == "POST":
        form = QuotationForm(request.POST, instance=doc)
        if form.is_valid():
            form.save()
            return redirect("quotes:quotation_detail", pk=doc.pk)
    else:
        form = QuotationForm(instance=doc)
    return render(request, "quotes/quotation_form.html", {"form": form, "document": doc})


def _quote_for_edit(pk: int) -> SalesDocument:
    return get_object_or_404(
        SalesDocument.objects.select_related(
            "customer", "contact", "salesperson", "deal", "bank_account"
        ).prefetch_related("lines__product", "lines__variant"),
        pk=pk,
        doc_type=DocType.QUOTATION,
    )


def _lines_ctx(doc: SalesDocument, *, add_form=None, editing_line_id=None, edit_form=None) -> dict:
    return {
        "document": doc,
        "totals": compute_document_totals(doc),
        "line_form": add_form or SalesDocLineForm(),
        "editing_line_id": editing_line_id,
        "line_edit_form": edit_form,
    }


@login_required
def quotation_detail(request: HttpRequest, pk: int) -> HttpResponse:
    doc = _quote_for_edit(pk)
    return render(request, "quotes/quotation_detail.html", _lines_ctx(doc))


@login_required
def quotation_lines_partial(request: HttpRequest, pk: int) -> HttpResponse:
    return render(request, "quotes/_quote_lines.html", _lines_ctx(_quote_for_edit(pk)))


@login_required
@require_POST
def quotation_add_line(request: HttpRequest, pk: int) -> HttpResponse:
    doc = _quote_for_edit(pk)
    form = SalesDocLineForm(request.POST)
    if form.is_valid():
        line = form.save(commit=False)
        line.document = doc
        line.position = (doc.lines.aggregate(m=Max("position"))["m"] or 0) + 1
        apply_catalog_defaults(line)
        line.save()
        return render(request, "quotes/_quote_lines.html", _lines_ctx(_quote_for_edit(pk)))
    return render(request, "quotes/_quote_lines.html", _lines_ctx(doc, add_form=form))


@login_required
@require_POST
def quotation_delete_line(request: HttpRequest, pk: int, line_pk: int) -> HttpResponse:
    doc = _quote_for_edit(pk)
    get_object_or_404(SalesDocLine, pk=line_pk, document=doc).delete()
    return render(request, "quotes/_quote_lines.html", _lines_ctx(_quote_for_edit(pk)))


@login_required
def quotation_line_edit(request: HttpRequest, pk: int, line_pk: int) -> HttpResponse:
    doc = _quote_for_edit(pk)
    line = get_object_or_404(SalesDocLine, pk=line_pk, document=doc)
    if request.method == "POST":
        form = SalesDocLineForm(request.POST, instance=line)
        if form.is_valid():
            obj = form.save(commit=False)
            apply_catalog_defaults(obj)
            obj.save()
            return render(request, "quotes/_quote_lines.html", _lines_ctx(_quote_for_edit(pk)))
        return render(
            request,
            "quotes/_quote_lines.html",
            _lines_ctx(doc, editing_line_id=line.pk, edit_form=form),
        )
    return render(
        request,
        "quotes/_quote_lines.html",
        _lines_ctx(doc, editing_line_id=line.pk, edit_form=SalesDocLineForm(instance=line)),
    )


@login_required
@require_POST
def quotation_from_deal(request: HttpRequest, deal_pk: int) -> HttpResponse:
    deal = get_object_or_404(Deal, pk=deal_pk)
    doc = create_quotation_from_deal(deal, salesperson=request.user)
    return redirect("quotes:quotation_detail", pk=doc.pk)


@login_required
def quotation_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(
        SalesDocument.objects.select_related(
            "customer", "contact", "salesperson", "bank_account"
        ).prefetch_related("lines"),
        pk=pk,
        doc_type=DocType.QUOTATION,
    )
    pdf = render_quotation_pdf(doc)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = (
        f'inline; filename="{doc.doc_number or f"quotation-{doc.pk}"}.pdf"'
    )
    return resp


# --- Sending / public share link ---------------------------------------------
def _public_quote_url(request: HttpRequest, token: str) -> str:
    from django.urls import reverse

    return request.build_absolute_uri(reverse("public_quotation", args=[token]))


@login_required
@require_POST
def quotation_send(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(
        SalesDocument.objects.select_related("contact", "deal", "customer", "salesperson"),
        pk=pk,
        doc_type=DocType.QUOTATION,
    )
    link = get_or_create_share_link(doc, created_by=request.user)
    mark_sent(doc)
    # auto follow-up task (to the salesperson, or unassigned if none)
    Task.objects.create(
        deal=doc.deal,
        customer=doc.customer,
        kind=TaskKind.FOLLOW_UP,
        description=f"ติดตามใบเสนอราคา {doc.doc_number}",
        due_at=timezone.now() + timedelta(days=7),
        assignee=doc.salesperson,
    )
    url = _public_quote_url(request, link.token)
    if doc.contact and doc.contact.email:
        send_mail(
            subject=f"ใบเสนอราคา {doc.doc_number}",
            message=f"เรียนคุณ {doc.contact.name}\n\nดูใบเสนอราคาได้ที่ลิงก์นี้: {url}\n\nขอบคุณครับ",
            from_email=None,
            recipient_list=[doc.contact.email],
            fail_silently=True,
        )
        messages.success(request, f"ส่งอีเมลถึง {doc.contact.email} แล้ว · ลิงก์: {url}")
    else:
        messages.success(request, f"สร้างลิงก์แชร์แล้ว · {url}")
    return redirect("quotes:quotation_detail", pk=doc.pk)


def _resolve_link(token: str) -> QuotationShareLink | None:
    link = (
        QuotationShareLink.objects.filter(token=token)
        .select_related(
            "document",
            "document__customer",
            "document__contact",
            "document__salesperson",
            "document__bank_account",
            "tenant",
        )
        .first()
    )
    return link if link is not None and link.is_valid() else None


def public_quotation(request: HttpRequest, token: str) -> HttpResponse:
    """Public, login-free quotation view. The tenant is resolved from the token."""
    link = _resolve_link(token)
    if link is None:
        return render(request, "quotes/public_quotation_invalid.html")
    from apps.tenants.models import CompanyProfile

    with tenant_context(link.tenant):
        doc = link.document
        ctx = {
            "document": doc,
            "totals": compute_document_totals(doc),
            "company": CompanyProfile.objects.filter(tenant_id=doc.tenant_id).first(),
            "token": token,
            "responses": CustomerResponse,
        }
        return render(request, "quotes/public_quotation.html", ctx)


@require_POST
def public_quotation_respond(request: HttpRequest, token: str) -> HttpResponse:
    link = _resolve_link(token)
    if link is None:
        return render(request, "quotes/public_quotation_invalid.html")
    response = request.POST.get("response", "")
    if response not in CustomerResponse.values:
        return redirect("public_quotation", token=token)
    with tenant_context(link.tenant):
        record_customer_response(
            link.document,
            response=response,
            signed_name=request.POST.get("signed_name", "").strip(),
            note=request.POST.get("note", "").strip(),
            ip=request.META.get("REMOTE_ADDR"),
        )
        return render(request, "quotes/public_quotation_thanks.html", {"document": link.document})


def public_quotation_pdf(request: HttpRequest, token: str) -> HttpResponse:
    link = _resolve_link(token)
    if link is None:
        return render(request, "quotes/public_quotation_invalid.html")
    with tenant_context(link.tenant):
        pdf = render_quotation_pdf(link.document)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = (
        f'inline; filename="{link.document.doc_number or "quotation"}.pdf"'
    )
    return resp
