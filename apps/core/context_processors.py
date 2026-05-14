from django.http import HttpRequest


def current_tenant(request: HttpRequest) -> dict:
    """Expose the active tenant + a couple of role flags to templates."""
    from .permissions import can_view_reports, is_manager

    notif_count = 0
    quota_warning: list = []
    plan_has_billing = False
    tenant = getattr(request, "tenant", None)
    user = getattr(request, "user", None)
    if tenant is not None and user is not None and getattr(user, "is_authenticated", False):
        try:
            from apps.crm.dashboard import build_notifications

            notif_count = len(build_notifications(request))
        except Exception:  # noqa: BLE001 — a broken feed must never break every page
            notif_count = 0
        try:
            from apps.tenants.quota import near_cap

            quota_warning = near_cap(tenant)
        except Exception:  # noqa: BLE001 — quota glitch must never break the page
            quota_warning = []
        try:
            from apps.tenants import plans as plan_registry

            plan_has_billing = plan_registry.get(tenant.plan).features.billing_module
        except Exception:  # noqa: BLE001 — bad config must never break the page
            plan_has_billing = False
    return {
        "current_tenant": tenant,
        "can_view_reports": can_view_reports(request),
        "is_manager": is_manager(request),
        "notif_count": notif_count,
        "quota_warning": quota_warning,
        "plan_has_billing": plan_has_billing,
    }
