from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.db.models import Q
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
