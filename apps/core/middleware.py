"""Resolves and activates the current tenant for each web request.

Resolution order:
  1. authenticated user -> their first active membership's tenant
  2. (TODO) subdomain -> tenant slug
  3. (dev only) settings.DEV_DEFAULT_TENANT_SLUG

Public, token-based flows (e.g. a customer viewing a quote via a share link) don't
go through here for tenant resolution — those views resolve the tenant from the token
and wrap their work in ``apps.core.current_tenant.tenant_context``.
"""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from .current_tenant import activate_tenant, deactivate_tenant


class CurrentTenantMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        tenant = self._resolve(request)
        request.tenant = tenant  # type: ignore[attr-defined]
        if tenant is not None:
            activate_tenant(tenant)
        try:
            return self.get_response(request)
        finally:
            deactivate_tenant()

    @staticmethod
    def _resolve(request: HttpRequest):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            membership = (
                user.memberships.select_related("tenant")
                .filter(is_active=True, tenant__is_active=True)
                .first()
            )
            if membership is not None:
                return membership.tenant

        # 2. subdomain -> tenant slug  (implement when we add subdomain routing)

        # 3. dev fallback
        if settings.DEBUG:
            slug = getattr(settings, "DEV_DEFAULT_TENANT_SLUG", "")
            if slug:
                from apps.tenants.models import Tenant

                return Tenant.objects.filter(slug=slug, is_active=True).first()
        return None
