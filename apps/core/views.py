from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render


def healthz(_request: HttpRequest) -> JsonResponse:
    """Tiny readiness probe — pings the DB and returns 200 OK. Hit by the deploy script
    + any uptime monitor. No tenant context required."""
    try:
        connection.ensure_connection()
        return JsonResponse({"status": "ok"})
    except Exception as exc:  # noqa: BLE001 — we want the body to carry the error class
        return JsonResponse({"status": "error", "detail": type(exc).__name__}, status=503)


def caddy_ask(request: HttpRequest) -> HttpResponse:
    """Caddy's on-demand TLS ``ask`` endpoint.

    Caddy calls this before minting a cert for a hostname it hasn't seen — we return 200 if
    the host maps to a known tenant (a platform host, a built-in ``<slug>.<APP_DOMAIN>``
    subdomain, or a verified ``TenantDomain`` row), else 404. This stops Caddy from issuing
    certs for random hostnames pointed at us by attackers.

    Wired at ``/_caddy/ask?domain=X``. No CSRF, no auth, no tenant resolution — it's a
    server-to-server call from Caddy on the same host.
    """
    from django.conf import settings as dj_settings

    from apps.tenants.models import Tenant, TenantDomain

    host = (request.GET.get("domain") or "").strip().lower()
    if not host:
        return HttpResponse(status=400)

    platform_hosts = {h.lower() for h in getattr(dj_settings, "PLATFORM_HOSTS", [])}
    if host in platform_hosts:
        return HttpResponse(status=200)

    app_domain = getattr(dj_settings, "APP_DOMAIN", "").lower()
    if app_domain and host.endswith("." + app_domain):
        slug = host[: -(len(app_domain) + 1)]
        if slug and "." not in slug and Tenant.objects.filter(slug=slug, is_active=True).exists():
            return HttpResponse(status=200)

    if TenantDomain.objects.filter(domain=host, verified=True, tenant__is_active=True).exists():
        return HttpResponse(status=200)

    return HttpResponse(status=404)


def home(request: HttpRequest) -> HttpResponse:
    """Landing page.

    On a tenant host (a verified custom domain or ``<slug>.<APP_DOMAIN>``) an anonymous
    visitor sees that tenant's public catalog/showroom — so ``wandeedee.com/`` shows
    Wandeedee's products with no login. Logged-in staff get the dashboard. On a platform
    host an anonymous visitor sees the salesdee.com marketing landing page.
    """
    if not request.user.is_authenticated:
        tenant = getattr(request, "tenant", None)
        if tenant is not None:
            from apps.catalog.views import public_home

            return public_home(request, tenant=tenant)
        return render(request, "core/landing.html")
    ctx: dict = {}
    if getattr(request, "tenant", None) is not None:
        from apps.crm.dashboard import build_dashboard
        from apps.tenants.views import onboarding_status

        ctx = build_dashboard(request)
        ob = onboarding_status(request)
        ctx["onboarding_remaining"] = ob["remaining"]
        ctx["onboarding_complete"] = ob["complete"]
    return render(request, "core/home.html", ctx)


@login_required
def search(request: HttpRequest) -> HttpResponse:
    """Global search across the current tenant's customers, deals, leads, quotations, products."""
    from apps.catalog.models import Product
    from apps.core.permissions import own_q
    from apps.crm.models import Customer, Deal, Lead
    from apps.quotes.models import SalesDocument

    q = (request.GET.get("q") or "").strip()
    results: dict[str, list] = {
        "customers": [],
        "deals": [],
        "leads": [],
        "quotations": [],
        "products": [],
    }
    if q:
        results["customers"] = list(
            Customer.objects.filter(
                Q(name__icontains=q) | Q(name_en__icontains=q) | Q(tax_id__icontains=q)
            ).order_by("name")[:10]
        )
        results["deals"] = list(
            Deal.objects.filter(own_q(request, "owner"), name__icontains=q)
            .select_related("customer", "stage")
            .order_by("-created_at")[:10]
        )
        results["leads"] = list(
            Lead.objects.filter(
                own_q(request, "assigned_to"),
            )
            .filter(Q(name__icontains=q) | Q(company_name__icontains=q))
            .order_by("-created_at")[:10]
        )
        results["quotations"] = list(
            SalesDocument.objects.filter(own_q(request, "salesperson"))
            .filter(Q(doc_number__icontains=q) | Q(reference__icontains=q))
            .select_related("customer")
            .order_by("-created_at")[:10]
        )
        results["products"] = list(
            Product.objects.filter(Q(name__icontains=q) | Q(code__icontains=q))
            .select_related("category")
            .order_by("name")[:10]
        )
    total = sum(len(v) for v in results.values())
    return render(request, "core/search.html", {"q": q, "results": results, "total": total})


@login_required
def notifications(request: HttpRequest) -> HttpResponse:
    from apps.crm.dashboard import build_notifications

    items = build_notifications(request)
    return render(request, "core/notifications.html", {"items": items})
