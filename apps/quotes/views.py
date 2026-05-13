from __future__ import annotations

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db.models import Max
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.current_tenant import tenant_context
from apps.core.permissions import own_q
from apps.crm.models import Deal, Task, TaskKind
from apps.integrations.line import LineNotConfigured, push_quotation_flex

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
    WorkflowError,
    apply_catalog_defaults,
    approve_quotation,
    can_approve,
    cancel_quotation,
    compute_document_totals,
    create_quotation_from_deal,
    get_or_create_share_link,
    mark_sent,
    next_document_number,
    record_customer_response,
    record_quote_viewed,
    reject_approval,
    reopen_quotation,
    submit_quotation,
)


def _visible_quotes(request: HttpRequest):
    """Quotations the requester may see — all of them, or only their own when their membership has
    ``can_see_all_records`` turned off (REQUIREMENTS.md §4.15)."""
    return SalesDocument.objects.filter(own_q(request, "salesperson"), doc_type=DocType.QUOTATION)


@login_required
def quotation_list(request: HttpRequest) -> HttpResponse:
    docs = (
        _visible_quotes(request)
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
            if doc.salesperson_id is None:
                doc.salesperson = request.user
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
    doc = get_object_or_404(_visible_quotes(request), pk=pk)
    if not doc.is_editable:
        messages.error(request, "เอกสารนี้ถูกล็อกแล้ว — กด “เปิดแก้ไขใหม่ (Rev.)” ก่อนจึงจะแก้ไขได้")
        return redirect("quotes:quotation_detail", pk=doc.pk)
    if request.method == "POST":
        form = QuotationForm(request.POST, instance=doc)
        if form.is_valid():
            form.save()
            return redirect("quotes:quotation_detail", pk=doc.pk)
    else:
        form = QuotationForm(instance=doc)
    return render(request, "quotes/quotation_form.html", {"form": form, "document": doc})


def _assert_lines_editable(doc: SalesDocument) -> None:
    if not doc.is_editable:
        raise PermissionDenied("เอกสารนี้ถูกล็อกแล้ว แก้ไขรายการไม่ได้")


def _quote_for_edit(request: HttpRequest, pk: int) -> SalesDocument:
    return get_object_or_404(
        _visible_quotes(request)
        .select_related("customer", "contact", "salesperson", "deal", "bank_account")
        .prefetch_related("lines__product", "lines__variant"),
        pk=pk,
    )


def _lines_ctx(doc: SalesDocument, *, add_form=None, editing_line_id=None, edit_form=None) -> dict:
    return {
        "document": doc,
        "totals": compute_document_totals(doc),
        "line_form": add_form or SalesDocLineForm(),
        "editing_line_id": editing_line_id,
        "line_edit_form": edit_form,
        "editable": doc.is_editable,
    }


@login_required
def quotation_detail(request: HttpRequest, pk: int) -> HttpResponse:
    doc = _quote_for_edit(request, pk)
    ctx = {
        **_lines_ctx(doc),
        "can_approve": can_approve(request.user, doc.tenant_id),
        "revisions": list(doc.revisions.all()),
    }
    return render(request, "quotes/quotation_detail.html", ctx)


@login_required
def quotation_revisions(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(
        _visible_quotes(request).prefetch_related("revisions__changed_by"), pk=pk
    )
    return render(
        request,
        "quotes/quotation_revisions.html",
        {"document": doc, "revisions": list(doc.revisions.all())},
    )


@login_required
def quotation_revision_detail(request: HttpRequest, pk: int, revision: int) -> HttpResponse:
    doc = get_object_or_404(_visible_quotes(request).prefetch_related("lines"), pk=pk)
    rev = get_object_or_404(doc.revisions, revision=revision)
    current = compute_document_totals(doc)
    return render(
        request,
        "quotes/quotation_revision_detail.html",
        {"document": doc, "rev": rev, "snap": rev.snapshot, "current_totals": current},
    )


@login_required
def quotation_lines_partial(request: HttpRequest, pk: int) -> HttpResponse:
    return render(request, "quotes/_quote_lines.html", _lines_ctx(_quote_for_edit(request, pk)))


@login_required
@require_POST
def quotation_add_line(request: HttpRequest, pk: int) -> HttpResponse:
    doc = _quote_for_edit(request, pk)
    _assert_lines_editable(doc)
    form = SalesDocLineForm(request.POST, request.FILES)
    if form.is_valid():
        line = form.save(commit=False)
        line.document = doc
        line.position = (doc.lines.aggregate(m=Max("position"))["m"] or 0) + 1
        apply_catalog_defaults(line)
        line.save()
        return render(request, "quotes/_quote_lines.html", _lines_ctx(_quote_for_edit(request, pk)))
    return render(request, "quotes/_quote_lines.html", _lines_ctx(doc, add_form=form))


@login_required
@require_POST
def quotation_delete_line(request: HttpRequest, pk: int, line_pk: int) -> HttpResponse:
    doc = _quote_for_edit(request, pk)
    _assert_lines_editable(doc)
    get_object_or_404(SalesDocLine, pk=line_pk, document=doc).delete()
    return render(request, "quotes/_quote_lines.html", _lines_ctx(_quote_for_edit(request, pk)))


@login_required
@require_POST
def quotation_reorder_lines(request: HttpRequest, pk: int) -> HttpResponse:
    """htmx/SortableJS: reassign ``position`` for a set of lines given as ``line=<pk>`` (repeated)
    in their new visual order. Only shuffles the position slots those lines already occupy, so
    dragging within one room/group leaves the rest of the document alone."""
    doc = _quote_for_edit(request, pk)
    _assert_lines_editable(doc)
    ids = [int(x) for x in request.POST.getlist("line") if x.isdigit()]
    lines = {ln.pk: ln for ln in doc.lines.filter(pk__in=ids)}
    ordered = [i for i in ids if i in lines]
    slots = sorted(lines[i].position for i in ordered)
    for slot, line_pk in zip(slots, ordered, strict=True):
        line = lines[line_pk]
        if line.position != slot:
            line.position = slot
            line.save(update_fields=["position"])
    return render(request, "quotes/_quote_lines.html", _lines_ctx(_quote_for_edit(request, pk)))


@login_required
def quotation_line_edit(request: HttpRequest, pk: int, line_pk: int) -> HttpResponse:
    doc = _quote_for_edit(request, pk)
    _assert_lines_editable(doc)
    line = get_object_or_404(SalesDocLine, pk=line_pk, document=doc)
    if request.method == "POST":
        form = SalesDocLineForm(request.POST, request.FILES, instance=line)
        if form.is_valid():
            obj = form.save(commit=False)
            apply_catalog_defaults(obj)
            obj.save()
            return render(
                request, "quotes/_quote_lines.html", _lines_ctx(_quote_for_edit(request, pk))
            )
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
    deal = get_object_or_404(Deal.objects.filter(own_q(request, "owner")), pk=deal_pk)
    doc = create_quotation_from_deal(deal, salesperson=request.user)
    return redirect("quotes:quotation_detail", pk=doc.pk)


@login_required
@require_POST
def quotation_from_lead_ai(request: HttpRequest, lead_pk: int) -> HttpResponse:
    """Draft a quotation from a lead's conversation using Claude (apps.integrations.ai), then open
    the editor for the salesperson to review. Needs ``settings.ANTHROPIC_API_KEY``."""
    from apps.catalog.models import Product
    from apps.crm.models import Lead
    from apps.integrations.ai import AINotConfigured, draft_quotation_from_text

    from .services import create_quotation_from_ai_draft

    lead = get_object_or_404(Lead.objects.filter(own_q(request, "assigned_to")), pk=lead_pk)
    conversation = lead.conversation_text()
    if not conversation:
        messages.error(request, "Lead นี้ยังไม่มีบทสนทนาให้ AI ใช้ร่างใบเสนอราคา")
        return redirect("crm:lead_detail", pk=lead.pk)
    catalog = [
        {"code": p.code, "name": p.name, "unit": p.unit, "price": str(p.default_price)}
        for p in Product.objects.filter(is_active=True).order_by("name")[:300]
    ]
    try:
        draft = draft_quotation_from_text(conversation, catalog=catalog)
    except AINotConfigured as exc:
        messages.error(request, str(exc))
        return redirect("crm:lead_detail", pk=lead.pk)
    except Exception as exc:  # noqa: BLE001 — surface API/network/parse errors, don't 500
        messages.error(request, f"AI ร่างใบเสนอราคาไม่สำเร็จ: {exc}")
        return redirect("crm:lead_detail", pk=lead.pk)
    doc = create_quotation_from_ai_draft(
        draft, salesperson=request.user, reference=lead.name, deal=lead.deal
    )
    messages.success(request, f"AI ร่างใบเสนอราคา {doc.doc_number} ให้แล้ว — โปรดตรวจสอบและแก้ไขก่อนส่ง")
    return redirect("quotes:quotation_detail", pk=doc.pk)


@login_required
def quotation_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(
        _visible_quotes(request)
        .select_related("customer", "contact", "salesperson", "bank_account")
        .prefetch_related("lines"),
        pk=pk,
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


# --- Status transitions -------------------------------------------------------
@login_required
@require_POST
def quotation_submit(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(_visible_quotes(request).prefetch_related("lines"), pk=pk)
    try:
        new_status = submit_quotation(doc, user=request.user)
    except WorkflowError as exc:
        messages.error(request, str(exc))
    else:
        if new_status == DocStatus.PENDING_APPROVAL:
            messages.warning(request, "ส่งขออนุมัติส่วนลดแล้ว — รอผู้จัดการอนุมัติก่อนจึงจะส่งให้ลูกค้าได้")
        else:
            messages.success(request, "เอกสารพร้อมส่งให้ลูกค้าแล้ว")
    return redirect("quotes:quotation_detail", pk=doc.pk)


@login_required
@require_POST
def quotation_approve(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(_visible_quotes(request), pk=pk)
    if not can_approve(request.user, doc.tenant_id):
        raise PermissionDenied("คุณไม่มีสิทธิ์อนุมัติส่วนลด")
    try:
        approve_quotation(doc, user=request.user)
    except WorkflowError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "อนุมัติส่วนลดแล้ว — พร้อมส่งให้ลูกค้า")
    return redirect("quotes:quotation_detail", pk=doc.pk)


@login_required
@require_POST
def quotation_reject_approval(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(_visible_quotes(request), pk=pk)
    if not can_approve(request.user, doc.tenant_id):
        raise PermissionDenied("คุณไม่มีสิทธิ์ตีกลับคำขออนุมัติ")
    try:
        reject_approval(doc, user=request.user, note=request.POST.get("note", "").strip())
    except WorkflowError as exc:
        messages.error(request, str(exc))
    else:
        messages.warning(request, "ตีกลับเป็นร่างแล้ว ให้พนักงานขายแก้ไขแล้วส่งใหม่")
    return redirect("quotes:quotation_detail", pk=doc.pk)


@login_required
@require_POST
def quotation_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(_visible_quotes(request), pk=pk)
    cancel_quotation(doc)
    messages.warning(request, "ยกเลิกเอกสารแล้ว")
    return redirect("quotes:quotation_detail", pk=doc.pk)


@login_required
@require_POST
def quotation_reopen(request: HttpRequest, pk: int) -> HttpResponse:
    doc = get_object_or_404(_visible_quotes(request), pk=pk)
    try:
        reopen_quotation(doc, reason=request.POST.get("reason", "").strip())
    except WorkflowError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"เปิดแก้ไขใหม่เป็น Rev.{doc.revision} (สถานะ: ร่าง)")
    return redirect("quotes:quotation_detail", pk=doc.pk)


def _quote_for_send(request: HttpRequest, pk: int) -> SalesDocument:
    return get_object_or_404(
        _visible_quotes(request)
        .select_related("contact", "deal", "customer", "salesperson")
        .prefetch_related("lines"),
        pk=pk,
    )


def _ensure_sendable(request: HttpRequest, doc: SalesDocument) -> str | None:
    """Get the quotation to a sendable state, or return a user-facing reason it can't be sent.
    A draft is auto-submitted first; if that needs approval, sending is blocked."""
    if doc.status in (DocStatus.DRAFT, DocStatus.PENDING_APPROVAL):
        try:
            new_status = submit_quotation(doc, user=request.user)
        except WorkflowError as exc:
            return str(exc)
        if new_status == DocStatus.PENDING_APPROVAL:
            return "ใบเสนอราคานี้มีส่วนลดเกินสิทธิ์ของคุณ — ต้องให้ผู้จัดการอนุมัติก่อนจึงจะส่งได้"
    elif doc.status not in (DocStatus.READY, DocStatus.SENT):
        return f"ส่งเอกสารในสถานะ “{doc.get_status_display()}” ไม่ได้"
    return None


def _finalize_sent(request: HttpRequest, doc: SalesDocument) -> None:
    """Mark the quotation SENT (snapshots a revision on the READY→SENT step) + drop a follow-up task."""
    mark_sent(doc, user=request.user)
    Task.objects.create(
        deal=doc.deal,
        customer=doc.customer,
        kind=TaskKind.FOLLOW_UP,
        description=f"ติดตามใบเสนอราคา {doc.doc_number}",
        due_at=timezone.now() + timedelta(days=7),
        assignee=doc.salesperson,
    )


@login_required
@require_POST
def quotation_send(request: HttpRequest, pk: int) -> HttpResponse:
    doc = _quote_for_send(request, pk)
    err = _ensure_sendable(request, doc)
    if err:
        messages.error(request, err)
        return redirect("quotes:quotation_detail", pk=doc.pk)
    link = get_or_create_share_link(doc, created_by=request.user)
    url = _public_quote_url(request, link.token)
    _finalize_sent(request, doc)
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


@login_required
@require_POST
def quotation_send_line(request: HttpRequest, pk: int) -> HttpResponse:
    """Send the quotation to the customer over LINE as a Flex 'card' (summary + open/PDF buttons).
    Recipient = the contact's LINE user id, or — if the quote was drafted from a chat — that thread.
    When sent into a source conversation, the send is also logged on that thread."""
    from apps.core.utils.thai_dates import format_thai_date

    doc = _quote_for_send(request, pk)
    recipient = (doc.contact.line_id if doc.contact else "") or (
        doc.source_conversation.external_id if doc.source_conversation else ""
    )
    if not recipient:
        messages.error(
            request, "ยังไม่รู้ LINE user ID ของลูกค้า — เพิ่มในข้อมูลผู้ติดต่อ หรือสร้างใบเสนอราคาจากแชต"
        )
        return redirect("quotes:quotation_detail", pk=doc.pk)
    err = _ensure_sendable(request, doc)
    if err:
        messages.error(request, err)
        return redirect("quotes:quotation_detail", pk=doc.pk)
    link = get_or_create_share_link(doc, created_by=request.user)
    url = _public_quote_url(request, link.token)
    pdf_url = request.build_absolute_uri(reverse("public_quotation_pdf", args=[link.token]))
    totals = compute_document_totals(doc)
    from apps.tenants.models import CompanyProfile

    profile = CompanyProfile.objects.filter(tenant_id=doc.tenant_id).first()
    try:
        push_quotation_flex(
            recipient,
            doc_number=doc.doc_number or "ใบเสนอราคา",
            customer_name=(doc.customer.name if doc.customer else (doc.reference or "")),
            total_text=f"{totals.grand_total:,.2f} บาท",
            valid_text=format_thai_date(doc.valid_until) if doc.valid_until else "—",
            view_url=url,
            pdf_url=pdf_url,
            company_name=profile.name_th if profile else "",
        )
    except LineNotConfigured as exc:
        messages.error(request, str(exc))
        return redirect("quotes:quotation_detail", pk=doc.pk)
    except Exception as exc:  # noqa: BLE001 — SDK/network error; surface it rather than 500
        messages.error(request, f"ส่งทาง LINE ไม่สำเร็จ: {exc}")
        return redirect("quotes:quotation_detail", pk=doc.pk)
    if doc.source_conversation_id:
        from apps.integrations.line import record_outbound_text

        record_outbound_text(
            doc.source_conversation, f"ส่งใบเสนอราคา {doc.doc_number} แล้ว", sender_user=request.user
        )
    _finalize_sent(request, doc)
    who = doc.contact.name if doc.contact else "ลูกค้า"
    messages.success(request, f"ส่งใบเสนอราคาทาง LINE ถึง {who} แล้ว · ลิงก์: {url}")
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
        record_quote_viewed(doc, ip=request.META.get("REMOTE_ADDR"))
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
