from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def home(request: HttpRequest) -> HttpResponse:
    """Landing page.

    On a tenant host (a verified custom domain or ``<slug>.<APP_DOMAIN>``) an anonymous
    visitor sees that tenant's public catalog/showroom — so ``wandeedee.com/`` shows
    Wandeedee's products with no login. Logged-in staff get the dashboard. On a platform
    host an anonymous visitor is sent to the login page (same as ``@login_required``).
    """
    if not request.user.is_authenticated:
        tenant = getattr(request, "tenant", None)
        if tenant is not None:
            from apps.catalog.views import public_home

            return public_home(request, tenant=tenant)
        return redirect_to_login(request.get_full_path())
    ctx: dict = {}
    if getattr(request, "tenant", None) is not None:
        from apps.crm.dashboard import build_dashboard
        from apps.tenants.views import onboarding_status

        ctx = build_dashboard(request)
        ob = onboarding_status(request)
        ctx["onboarding_remaining"] = ob["remaining"]
        ctx["onboarding_complete"] = ob["complete"]
    return render(request, "core/home.html", ctx)
