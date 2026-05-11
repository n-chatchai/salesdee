from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.crm.models import Deal

from .forms import QuotationForm, SalesDocLineForm
from .models import DocStatus, DocType, SalesDocLine, SalesDocument
from .services import compute_document_totals, create_quotation_from_deal, next_document_number


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


@login_required
def quotation_detail(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(
        SalesDocument.objects.select_related(
            "customer", "contact", "salesperson", "deal", "bank_account"
        ).prefetch_related("lines"),
        pk=pk,
        doc_type=DocType.QUOTATION,
    )
    return render(
        request,
        "quotes/quotation_detail.html",
        {"document": doc, "totals": compute_document_totals(doc), "line_form": SalesDocLineForm()},
    )


@login_required
@require_POST
def quotation_add_line(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(SalesDocument, pk=pk, doc_type=DocType.QUOTATION)
    form = SalesDocLineForm(request.POST)
    if form.is_valid():
        line = form.save(commit=False)
        line.document = doc
        line.position = (doc.lines.aggregate(m=Max("position"))["m"] or 0) + 1
        line.save()
        return redirect("quotes:quotation_detail", pk=doc.pk)
    return render(
        request,
        "quotes/quotation_detail.html",
        {"document": doc, "totals": compute_document_totals(doc), "line_form": form},
    )


@login_required
@require_POST
def quotation_delete_line(request: HttpRequest, pk: int, line_pk: int) -> HttpResponse:
    doc = get_object_or_404(SalesDocument, pk=pk, doc_type=DocType.QUOTATION)
    get_object_or_404(SalesDocLine, pk=line_pk, document=doc).delete()
    return redirect("quotes:quotation_detail", pk=doc.pk)


@login_required
@require_POST
def quotation_from_deal(request: HttpRequest, deal_pk: int) -> HttpResponse:
    deal = get_object_or_404(Deal, pk=deal_pk)
    doc = create_quotation_from_deal(deal, salesperson=request.user)
    return redirect("quotes:quotation_detail", pk=doc.pk)
