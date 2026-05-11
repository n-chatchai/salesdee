"""Resolves and activates the current tenant for each web request.

Resolution order:
  1. **host** — a verified custom domain, or the built-in subdomain ``<slug>.<APP_DOMAIN>``.
     (Requests to a ``PLATFORM_HOSTS`` host resolve no tenant — that's the marketing/app site.)
  2. authenticated user → their first active membership's tenant (covers logged-in requests to a
     platform host, and the single-tenant dev setup).
  3. (dev only) ``settings.DEV_DEFAULT_TENANT_SLUG``.

If the host resolves a tenant and the logged-in user is **not** a member of it → 403 (don't let a
user of one workspace see another's data just by visiting its domain).

Custom domains require DNS (CNAME → the app) and on-demand TLS — that's a deployment concern.
"""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.core.exceptions import PermissionDenied
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

    def _resolve(self, request: HttpRequest):
        host = request.get_host().split(":")[0].lower()
        user = getattr(request, "user", None)
        authed = user is not None and user.is_authenticated

        tenant = self._tenant_from_host(host)
        if tenant is not None:
            if (
                authed
                and user is not None
                and not user.memberships.filter(tenant=tenant, is_active=True).exists()
            ):
                raise PermissionDenied("คุณไม่มีสิทธิ์เข้าถึง workspace นี้")
            return tenant

        if authed and user is not None:
            membership = (
                user.memberships.select_related("tenant")
                .filter(is_active=True, tenant__is_active=True)
                .first()
            )
            if membership is not None:
                return membership.tenant

        if settings.DEBUG:
            slug = getattr(settings, "DEV_DEFAULT_TENANT_SLUG", "")
            if slug:
                from apps.tenants.models import Tenant

                return Tenant.objects.filter(slug=slug, is_active=True).first()
        return None

    @staticmethod
    def _tenant_from_host(host: str):
        platform_hosts = {h.lower() for h in getattr(settings, "PLATFORM_HOSTS", [])}
        if host in platform_hosts:
            return None
        from apps.tenants.models import Tenant, TenantDomain

        app_domain = getattr(settings, "APP_DOMAIN", "").lower()
        if app_domain and host.endswith("." + app_domain):
            slug = host[: -(len(app_domain) + 1)]
            if slug and "." not in slug:  # only one label deep
                return Tenant.objects.filter(slug=slug, is_active=True).first()
        td = (
            TenantDomain.objects.filter(domain=host, verified=True, tenant__is_active=True)
            .select_related("tenant")
            .first()
        )
        return td.tenant if td is not None else None
