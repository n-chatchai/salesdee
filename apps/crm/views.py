from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .models import Customer, Deal, DealStatus, PipelineStage
from .services import move_deal_to_stage


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
        request,
        "crm/pipeline.html",
        {"columns": columns, "unassigned_count": unassigned},
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


@login_required
def customer_list(request: HttpRequest) -> HttpResponse:
    customers = (
        Customer.objects.filter(is_archived=False)
        .annotate(deal_count=Count("deals"))
        .order_by("name")
    )
    return render(request, "crm/customers.html", {"customers": customers})


@login_required
def deal_detail(request: HttpRequest, pk: int) -> HttpResponse:
    deal = get_object_or_404(
        Deal.objects.select_related("customer", "contact", "stage", "owner"), pk=pk
    )
    activities = deal.activities.select_related("contact", "created_by").order_by("-occurred_at")
    tasks = deal.tasks.select_related("assignee").order_by("status", "due_at")
    return render(
        request,
        "crm/deal_detail.html",
        {"deal": deal, "activities": activities, "tasks": tasks},
    )
