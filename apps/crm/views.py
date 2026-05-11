from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ActivityForm, CustomerForm, DealForm, TaskForm
from .models import Customer, Deal, DealStatus, PipelineStage, Task, TaskStatus
from .services import move_deal_to_stage


# --- Pipeline -----------------------------------------------------------------
@login_required
def pipeline(request: HttpRequest) -> HttpResponse:
    """Kanban board: a column per pipeline stage, cards = open deals in that stage."""
    stages = list(PipelineStage.objects.order_by("order"))
    open_deals = (
        Deal.objects.filter(status=DealStatus.OPEN, stage__isnull=False)
        .select_related("customer", "owner", "stage")
        .order_by("-created_at")
    )
    by_stage: dict[int, list[Deal]] = {s.pk: [] for s in stages}
    for deal in open_deals:
        sid = deal.stage_id
        if sid is not None:
            by_stage.setdefault(sid, []).append(deal)
    columns = [(s, by_stage.get(s.pk, [])) for s in stages]
    unassigned = Deal.objects.filter(status=DealStatus.OPEN, stage__isnull=True).count()
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
    deal = get_object_or_404(Deal, pk=deal_id)
    stage = get_object_or_404(PipelineStage, pk=stage_id)
    move_deal_to_stage(deal, stage)
    return HttpResponse(status=204)


# --- Deals --------------------------------------------------------------------
@login_required
def deal_detail(request: HttpRequest, pk: int) -> HttpResponse:
    deal = get_object_or_404(
        Deal.objects.select_related("customer", "contact", "stage", "owner"), pk=pk
    )
    return render(
        request,
        "crm/deal_detail.html",
        {
            "deal": deal,
            "activities": _deal_activities(deal),
            "tasks": _deal_tasks(deal),
            "activity_form": ActivityForm(customer=deal.customer),
            "task_form": TaskForm(initial={"assignee": request.user}),
        },
    )


@login_required
def deal_create(request: HttpRequest) -> HttpResponse:
    return _deal_form(request, instance=None)


@login_required
def deal_edit(request: HttpRequest, pk: int) -> HttpResponse:
    return _deal_form(request, instance=get_object_or_404(Deal, pk=pk))


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
    deal = get_object_or_404(Deal.objects.select_related("customer"), pk=pk)
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
    deal = get_object_or_404(Deal.objects.select_related("customer"), pk=pk)
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
    customer = get_object_or_404(Customer, pk=pk)
    return render(
        request,
        "crm/customer_detail.html",
        {
            "customer": customer,
            "contacts": customer.contacts.all(),
            "deals": customer.deals.select_related("stage").order_by("-created_at"),
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
