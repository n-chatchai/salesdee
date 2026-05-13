"""In-app audit-log view (FR-15.5). Manager/admin-only — others get 403."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import render

from apps.core.permissions import is_manager

from .models import AuditEvent


@login_required
def audit_log(request: HttpRequest) -> HttpResponse:
    if not is_manager(request):
        return HttpResponseForbidden("เฉพาะผู้จัดการและเจ้าของ workspace เท่านั้น")
    qs = AuditEvent.objects.select_related("actor").order_by("-created_at")
    action = request.GET.get("action", "").strip()
    actor = request.GET.get("actor", "").strip()
    if action:
        qs = qs.filter(action=action)
    if actor:
        qs = qs.filter(actor__email__icontains=actor)
    events = list(qs[:200])
    actions = list(
        AuditEvent.objects.values_list("action", flat=True).distinct().order_by("action")
    )
    return render(
        request,
        "audit/log.html",
        {"events": events, "actions": actions, "f_action": action, "f_actor": actor},
    )
