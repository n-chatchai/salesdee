"""Gate `/billing/*` behind the plan's billing-module feature flag.

The whole billing app (tax invoice / receipt / CN / DN / AR / statements / sales-tax report)
is a paid feature — Pro tier and above. Tenants on Starter / Growth see an upgrade page
when they hit any `/billing/*` URL.

Registered in ``config/settings/base.py``'s MIDDLEWARE.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


class BillingFeatureGateMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path.startswith("/billing/"):
            tenant = getattr(request, "tenant", None)
            if tenant is not None:
                from apps.tenants import plans as plan_registry
                from apps.tenants.features import feature_enabled

                if not feature_enabled(tenant, "billing"):
                    return render(
                        request,
                        "billing/upgrade_required.html",
                        {"current_plan": plan_registry.get(tenant.plan)},
                        status=402,
                    )
        return self.get_response(request)
