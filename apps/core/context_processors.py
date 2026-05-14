from django.http import HttpRequest


def current_tenant(request: HttpRequest) -> dict:
    """Expose the active tenant + a couple of role flags to templates."""
    from .permissions import can_view_reports, is_manager

    notif_count = 0
    quota_warning: list = []
    user = getattr(request, "user", None)
    if (
        getattr(request, "tenant", None) is not None
        and user is not None
        and getattr(user, "is_authenticated", False)
    ):
        try:
            from apps.crm.dashboard import build_notifications

            notif_count = len(build_notifications(request))
        except Exception:  # noqa: BLE001 — a broken feed must never break every page
            notif_count = 0
        try:
            from apps.tenants.quota import near_cap

            # request.tenant is set by CurrentTenantMiddleware (see apps/core/middleware.py).
            quota_warning = near_cap(request.tenant)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 — quota glitch must never break the page
            quota_warning = []
    return {
        "current_tenant": getattr(request, "tenant", None),
        "can_view_reports": can_view_reports(request),
        "is_manager": is_manager(request),
        "notif_count": notif_count,
        "quota_warning": quota_warning,
    }
