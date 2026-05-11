from django.http import HttpRequest


def current_tenant(request: HttpRequest) -> dict:
    """Expose the active tenant to templates as ``current_tenant``."""
    return {"current_tenant": getattr(request, "tenant", None)}
