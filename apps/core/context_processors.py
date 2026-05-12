from django.http import HttpRequest


def current_tenant(request: HttpRequest) -> dict:
    """Expose the active tenant + a couple of role flags to templates."""
    from .permissions import can_view_reports, is_manager

    return {
        "current_tenant": getattr(request, "tenant", None),
        "can_view_reports": can_view_reports(request),
        "is_manager": is_manager(request),
    }
