from __future__ import annotations

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.permissions import can_view_reports, own_q

from .forms import ActivityForm, CustomerForm, DealForm, LeadForm, LeadIntakeForm, TaskForm
from .models import (
    Customer,
    Deal,
    DealStatus,
    Lead,
    LeadChannel,
    LeadStatus,
    PipelineStage,
    Task,
    TaskStatus,
)
from .reports import build_reports
from .services import convert_lead, move_deal_to_stage


# --- Pipeline -----------------------------------------------------------------
@login_required
def pipeline(request: HttpRequest) -> HttpResponse:
    """Kanban board: a column per pipeline stage, cards = open deals in that stage."""
    mine = own_q(request, "owner")
    stages = list(PipelineStage.objects.order_by("order"))
    open_deals = (
        Deal.objects.filter(mine, status=DealStatus.OPEN, stage__isnull=False)
        .select_related("customer", "owner", "stage")
        .order_by("-created_at")
    )
    by_stage: dict[int, list[Deal]] = {s.pk: [] for s in stages}
    for deal in open_deals:
        sid = deal.stage_id
        if sid is not None:
            by_stage.setdefault(sid, []).append(deal)
    columns = [(s, by_stage.get(s.pk, [])) for s in stages]
    unassigned = Deal.objects.filter(mine, status=DealStatus.OPEN, stage__isnull=True).count()
    return render(
        request, "crm/pipeline.html", {"columns": columns, "unassigned_count": unassigned}
    )


@login_required
@require_POST
def move_deal(request: HttpRequest) -> HttpResponse:
    """htmx/SortableJS endpoint: move a deal to another stage (within the current tenant)."""
    deal_id = request.POST.get("deal_id")
    stage_id = request.POST.get("stage_id")
    if not deal_id or not stage_id:
        return HttpResponseBadRequest("deal_id and stage_id required")
    deal = get_object_or_404(Deal.objects.filter(own_q(request, "owner")), pk=deal_id)
    stage = get_object_or_404(PipelineStage, pk=stage_id)
    move_deal_to_stage(deal, stage)
    return HttpResponse(status=204)


# --- Deals --------------------------------------------------------------------
@login_required
def deal_detail(request: HttpRequest, pk: int) -> HttpResponse:
    deal = get_object_or_404(
        Deal.objects.filter(own_q(request, "owner")).select_related(
            "customer", "contact", "stage", "owner"
        ),
        pk=pk,
    )
    return render(
        request,
        "crm/deal_detail.html",
        {
            "deal": deal,
            "activities": _deal_activities(deal),
            "tasks": _deal_tasks(deal),
            "next_step": _deal_next_step(deal),
            "activity_form": ActivityForm(customer=deal.customer),
            "task_form": TaskForm(initial={"assignee": request.user}),
        },
    )


def _deal_next_step(deal: Deal) -> str | None:
    """A rule-based (not AI) "what to do next" hint for a deal. Highest-priority match wins."""
    from apps.quotes.models import DocStatus, DocType

    today = date.today()
    quotes = list(deal.documents.filter(doc_type=DocType.QUOTATION).order_by("-created_at"))
    # 1. A sent quotation the customer keeps opening but hasn't responded to.
    for q in quotes:
        if q.status == DocStatus.SENT and not q.customer_response and (q.view_count or 0) >= 3:
            return f"ลูกค้าเปิดดูใบเสนอราคา {q.doc_number or '#' + str(q.pk)} แล้ว {q.view_count} ครั้ง — ลองโทร/ทักไปถามว่าตัดสินใจอย่างไร"
    # 2. A quotation expiring within 5 days.
    for q in quotes:
        if (
            q.status in (DocStatus.READY, DocStatus.SENT)
            and q.valid_until
            and today <= q.valid_until <= today + timedelta(days=5)
        ):
            return f"ใบเสนอราคา {q.doc_number or '#' + str(q.pk)} ใกล้หมดอายุ ({q.valid_until}) — ติดตามด่วน"
    # 3. No quotation yet.
    if not quotes:
        return "ยังไม่มีใบเสนอราคาในดีลนี้ — ลองสร้างใบเสนอราคาจากดีลนี้"
    # 4. No activity in 7+ days.
    last = deal.activities.order_by("-occurred_at").first()
    if last is None or (timezone.now() - last.occurred_at).days >= 7:
        days = (timezone.now() - last.occurred_at).days if last else None
        return (
            f"ไม่มีความเคลื่อนไหว {days} วันแล้ว — บันทึกการติดตามล่าสุด"
            if days is not None
            else "ยังไม่มีบันทึกกิจกรรม — บันทึกการติดตามครั้งแรก"
        )
    return None


@login_required
def deal_create(request: HttpRequest) -> HttpResponse:
    return _deal_form(request, instance=None)


@login_required
def deal_edit(request: HttpRequest, pk: int) -> HttpResponse:
    return _deal_form(
        request, instance=get_object_or_404(Deal.objects.filter(own_q(request, "owner")), pk=pk)
    )


def _deal_form(request: HttpRequest, *, instance: Deal | None) -> HttpResponse:
    if request.method == "POST":
        form = DealForm(request.POST, instance=instance)
        if form.is_valid():
            deal = form.save(commit=False)
            if deal.stage is not None:
                deal.probability = deal.stage.default_probability
            deal.save()
            return redirect("crm:deal_detail", pk=deal.pk)
    else:
        form = DealForm(instance=instance)
    return render(request, "crm/deal_form.html", {"form": form, "deal": instance})


@login_required
@require_POST
def deal_log_activity(request: HttpRequest, pk: int) -> HttpResponse:
    deal = get_object_or_404(
        Deal.objects.filter(own_q(request, "owner")).select_related("customer"), pk=pk
    )
    form = ActivityForm(request.POST, customer=deal.customer)
    if form.is_valid():
        activity = form.save(commit=False)
        activity.deal = deal
        activity.customer = deal.customer
        activity.created_by = request.user
        activity.occurred_at = timezone.now()
        activity.save()
    return render(request, "crm/_activity_list.html", {"activities": _deal_activities(deal)})


@login_required
@require_POST
def deal_add_task(request: HttpRequest, pk: int) -> HttpResponse:
    deal = get_object_or_404(
        Deal.objects.filter(own_q(request, "owner")).select_related("customer"), pk=pk
    )
    form = TaskForm(request.POST)
    if form.is_valid():
        task = form.save(commit=False)
        task.deal = deal
        task.customer = deal.customer
        task.save()
    return render(request, "crm/_task_list.html", {"tasks": _deal_tasks(deal)})


def _deal_activities(deal: Deal):
    return deal.activities.select_related("contact", "created_by").order_by("-occurred_at")


def _deal_tasks(deal: Deal):
    return deal.tasks.select_related("assignee").order_by("status", "due_at")


# --- Customers ----------------------------------------------------------------
@login_required
def customer_list(request: HttpRequest) -> HttpResponse:
    customers = (
        Customer.objects.filter(is_archived=False)
        .annotate(deal_count=Count("deals"))
        .order_by("name")
    )
    return render(request, "crm/customers.html", {"customers": customers})


@login_required
def customer_detail(request: HttpRequest, pk: int) -> HttpResponse:
    from apps.quotes.models import DocType

    customer = get_object_or_404(Customer, pk=pk)
    return render(
        request,
        "crm/customer_detail.html",
        {
            "customer": customer,
            "contacts": customer.contacts.all(),
            "deals": customer.deals.filter(own_q(request, "owner"))
            .select_related("stage")
            .order_by("-created_at"),
            "quotations": customer.documents.filter(
                own_q(request, "salesperson"), doc_type=DocType.QUOTATION
            ).order_by("-created_at"),
            "conversations": customer.conversations.order_by("-last_message_at"),
            "activities": customer.activities.select_related("created_by", "deal").order_by(
                "-occurred_at"
            )[:30],
            "tasks": customer.tasks.select_related("assignee")
            .filter(status=TaskStatus.OPEN)
            .order_by("due_at"),
        },
    )


@login_required
def customer_create(request: HttpRequest) -> HttpResponse:
    return _customer_form(request, instance=None)


@login_required
def customer_edit(request: HttpRequest, pk: int) -> HttpResponse:
    return _customer_form(request, instance=get_object_or_404(Customer, pk=pk))


def _customer_form(request: HttpRequest, *, instance: Customer | None) -> HttpResponse:
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=instance)
        if form.is_valid():
            customer = form.save()
            return redirect("crm:customer_detail", pk=customer.pk)
    else:
        form = CustomerForm(instance=instance)
    return render(request, "crm/customer_form.html", {"form": form, "customer": instance})


# --- Tasks ("my work") --------------------------------------------------------
@login_required
def task_list(request: HttpRequest) -> HttpResponse:
    now = timezone.now()
    tasks = (
        Task.objects.filter(assignee_id=request.user.pk, status=TaskStatus.OPEN)
        .select_related("deal", "customer")
        .order_by("due_at")
    )
    return render(request, "crm/tasks.html", {"tasks": tasks, "now": now})


@login_required
@require_POST
def task_done(request: HttpRequest, pk: int) -> HttpResponse:
    task = get_object_or_404(Task.objects.select_related("deal", "customer"), pk=pk)
    task.status = TaskStatus.DONE
    task.completed_at = timezone.now()
    task.save()
    return render(request, "crm/_task_row.html", {"task": task, "now": timezone.now()})


# --- Leads --------------------------------------------------------------------
@login_required
def lead_list(request: HttpRequest) -> HttpResponse:
    leads = (
        Lead.objects.filter(own_q(request, "assigned_to"))
        .select_related("assigned_to")
        .order_by("-created_at")
    )
    new_count = leads.filter(status=LeadStatus.NEW).count()
    return render(request, "crm/leads.html", {"leads": leads, "new_count": new_count})


@login_required
def lead_detail(request: HttpRequest, pk: int) -> HttpResponse:
    from apps.integrations.ai import ai_is_configured

    lead = get_object_or_404(
        Lead.objects.filter(own_q(request, "assigned_to")).select_related(
            "assigned_to", "customer", "deal"
        ),
        pk=pk,
    )
    activities = list(lead.activities.select_related("created_by").order_by("-occurred_at")[:50])
    has_conversation = bool(lead.message) or any(a.body for a in activities)
    return render(
        request,
        "crm/lead_detail.html",
        {
            "lead": lead,
            "activities": activities,
            "ai_enabled": ai_is_configured() and has_conversation,
        },
    )


@login_required
def lead_create(request: HttpRequest) -> HttpResponse:
    return _lead_form(request, instance=None)


@login_required
def lead_edit(request: HttpRequest, pk: int) -> HttpResponse:
    return _lead_form(
        request,
        instance=get_object_or_404(Lead.objects.filter(own_q(request, "assigned_to")), pk=pk),
    )


def _lead_form(request: HttpRequest, *, instance: Lead | None) -> HttpResponse:
    if request.method == "POST":
        form = LeadForm(request.POST, instance=instance)
        if form.is_valid():
            lead = form.save()
            return redirect("crm:lead_detail", pk=lead.pk)
    else:
        form = LeadForm(instance=instance)
    return render(request, "crm/lead_form.html", {"form": form, "lead": instance})


@login_required
@require_POST
def lead_convert(request: HttpRequest, pk: int) -> HttpResponse:
    lead = get_object_or_404(
        Lead.objects.filter(own_q(request, "assigned_to")).select_related("deal"), pk=pk
    )
    if lead.status == LeadStatus.CONVERTED and lead.deal_id:
        return redirect("crm:deal_detail", pk=lead.deal_id)
    deal = convert_lead(lead, owner=request.user)
    return redirect("crm:deal_detail", pk=deal.pk)


# --- AI assistant on a lead ---------------------------------------------------
def _company_name(request: HttpRequest) -> str:
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        return ""
    from apps.tenants.models import CompanyProfile

    profile = CompanyProfile.objects.filter(tenant=tenant).first()
    return profile.name_th if profile else tenant.name


@login_required
@require_POST
def lead_suggest_reply(request: HttpRequest, pk: int) -> HttpResponse:
    """htmx: Claude drafts the next reply to the customer based on this lead's conversation."""
    from apps.integrations.ai import AINotConfigured, draft_reply_from_text
    from apps.integrations.line import line_is_configured

    lead = get_object_or_404(Lead.objects.filter(own_q(request, "assigned_to")), pk=pk)
    conversation = lead.conversation_text()
    if not conversation:
        return render(
            request, "crm/_ai_reply.html", {"lead": lead, "error": "ยังไม่มีบทสนทนาให้ AI ใช้"}
        )
    try:
        text = draft_reply_from_text(conversation, company_name=_company_name(request))
    except AINotConfigured as exc:
        return render(request, "crm/_ai_reply.html", {"lead": lead, "error": str(exc)})
    except Exception as exc:  # noqa: BLE001 — surface API/network errors instead of 500
        return render(
            request, "crm/_ai_reply.html", {"lead": lead, "error": f"AI ร่างข้อความไม่สำเร็จ: {exc}"}
        )
    return render(
        request,
        "crm/_ai_reply.html",
        {"lead": lead, "text": text, "can_send_line": bool(lead.line_id) and line_is_configured()},
    )


@login_required
@require_POST
def lead_send_line_reply(request: HttpRequest, pk: int) -> HttpResponse:
    """Send a (possibly AI-drafted, possibly edited) reply to the lead's LINE user."""
    from apps.integrations.line import LineNotConfigured, push_text

    from .models import Activity, ActivityKind

    lead = get_object_or_404(Lead.objects.filter(own_q(request, "assigned_to")), pk=pk)
    text = (request.POST.get("text") or "").strip()
    if not text:
        messages.error(request, "ไม่มีข้อความให้ส่ง")
        return redirect("crm:lead_detail", pk=lead.pk)
    if not lead.line_id:
        messages.error(request, "Lead นี้ยังไม่มี LINE user ID")
        return redirect("crm:lead_detail", pk=lead.pk)
    try:
        push_text(lead.line_id, text)
    except LineNotConfigured as exc:
        messages.error(request, str(exc))
        return redirect("crm:lead_detail", pk=lead.pk)
    except Exception as exc:  # noqa: BLE001 — surface SDK/network errors instead of 500
        messages.error(request, f"ส่งทาง LINE ไม่สำเร็จ: {exc}")
        return redirect("crm:lead_detail", pk=lead.pk)
    assert request.user.is_authenticated  # @login_required guarantees this; narrows the type
    Activity.objects.create(lead=lead, kind=ActivityKind.LINE, body=text, created_by=request.user)
    messages.success(request, "ส่งข้อความทาง LINE แล้ว")
    return redirect("crm:lead_detail", pk=lead.pk)


# --- Reports ------------------------------------------------------------------
def _reports_period(request: HttpRequest) -> tuple[str, date, date]:
    today = date.today()
    period = request.GET.get("period", "month")
    if period == "year":
        return "year", today.replace(month=1, day=1), today
    if period == "90d":
        return "90d", today - timedelta(days=90), today
    return "month", today.replace(day=1), today


@login_required
def reports(request: HttpRequest) -> HttpResponse:
    if not can_view_reports(request):
        raise PermissionDenied("รายงานเปิดให้เฉพาะเจ้าของ / ผู้จัดการ / ฝ่ายบัญชี")
    period, start, end = _reports_period(request)
    data = build_reports(start, end)
    if request.GET.get("export") == "xlsx":
        return _reports_xlsx(data)
    return render(request, "crm/reports.html", {**data, "period": period})


def _reports_xlsx(data: dict) -> HttpResponse:
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "ยอดขายตามเซลส์"
    ws.append(
        ["พนักงานขาย", "ดีลที่ปิดได้", "มูลค่าที่ปิดได้", "ใบเสนอราคาที่ส่ง", "ลูกค้าตอบรับ", "อัตราปิด %", "เป้าเดือนนี้"]
    )
    for r in data["by_salesperson"]:
        ws.append(
            [
                r["name"],
                r["won_count"],
                float(r["won_value"] or 0),
                r["quotes_sent"],
                r["quotes_accepted"],
                r["conv_rate"] if r["conv_rate"] is not None else "",
                float(r["target"]) if r["target"] is not None else "",
            ]
        )
    ws2 = wb.create_sheet("ตามช่องทาง")
    ws2.append(["ช่องทาง", "Lead ใหม่", "ดีลที่ปิดได้", "มูลค่าที่ปิดได้"])
    for r in data["by_channel"]:
        ws2.append([r["label"], r["leads"], r["won_deals"], float(r["won_value"] or 0)])
    buf = BytesIO()
    wb.save(buf)
    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = (
        f'attachment; filename="sales-report-{data["start"]}-{data["end"]}.xlsx"'
    )
    return resp


def lead_intake(request: HttpRequest, tenant_slug: str) -> HttpResponse:
    """Public 'request a quote / contact us' form for a tenant. No login. Tenant from the URL."""
    from apps.core.current_tenant import tenant_context
    from apps.tenants.models import Tenant

    tenant = get_object_or_404(Tenant, slug=tenant_slug, is_active=True)
    with tenant_context(tenant):
        if request.method == "POST":
            form = LeadIntakeForm(request.POST)
            if form.is_valid():
                lead = form.save(commit=False)
                lead.channel = LeadChannel.WEB_FORM
                lead.source = "intake form"
                lead.save()
                return render(request, "crm/intake_thanks.html", {"tenant": tenant})
        else:
            product = request.GET.get("product", "").strip()[:255]
            form = LeadIntakeForm(initial={"product_interest": product} if product else None)
        return render(request, "crm/intake.html", {"form": form, "tenant": tenant})
