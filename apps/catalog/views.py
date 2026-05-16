from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.current_tenant import tenant_context

from .forms import ProductCategoryForm, ProductForm
from .models import Product, ProductCategory


@login_required
def product_list(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    products = Product.objects.select_related("category").order_by("name")
    if q:
        products = products.filter(Q(name__icontains=q) | Q(code__icontains=q))
    return render(request, "catalog/products.html", {"products": products, "q": q})


@login_required
def product_detail(request: HttpRequest, pk: int) -> HttpResponse:
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related(
            "images", "variants", "options", "bundle_items__component", "bundle_items__variant"
        ),
        pk=pk,
    )
    return render(request, "catalog/product_detail.html", {"product": product})


@login_required
def product_create(request: HttpRequest) -> HttpResponse:
    return _product_form(request, instance=None)


@login_required
def product_edit(request: HttpRequest, pk: int) -> HttpResponse:
    return _product_form(request, instance=get_object_or_404(Product, pk=pk))


def _product_form(request: HttpRequest, *, instance: Product | None) -> HttpResponse:
    if request.method == "POST":
        form = ProductForm(request.POST, instance=instance)
        if form.is_valid():
            product = form.save()
            return redirect("catalog:product_detail", pk=product.pk)
    else:
        form = ProductForm(instance=instance)
    return render(request, "catalog/product_form.html", {"form": form, "product": instance})


# --- Categories ---------------------------------------------------------------
@login_required
def categories(request: HttpRequest) -> HttpResponse:
    cats = ProductCategory.objects.select_related("parent").annotate(
        product_count=Count("products")
    )
    # Parents first, then their children directly under them.
    by_parent: dict[int | None, list[ProductCategory]] = {}
    for c in cats:
        by_parent.setdefault(c.parent_id, []).append(c)
    ordered: list[ProductCategory] = []
    for root in by_parent.get(None, []):
        ordered.append(root)
        ordered.extend(by_parent.get(root.pk, []))
    # Any orphans whose parent fell outside (shouldn't happen) — append at the end.
    seen = {c.pk for c in ordered}
    ordered.extend(c for c in cats if c.pk not in seen)
    return render(request, "catalog/categories.html", {"categories": ordered})


@login_required
def category_create(request: HttpRequest) -> HttpResponse:
    return _category_form(request, instance=None)


@login_required
def category_edit(request: HttpRequest, pk: int) -> HttpResponse:
    return _category_form(request, instance=get_object_or_404(ProductCategory, pk=pk))


def _category_form(request: HttpRequest, *, instance: ProductCategory | None) -> HttpResponse:
    if request.method == "POST":
        form = ProductCategoryForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            return redirect("catalog:categories")
    else:
        form = ProductCategoryForm(instance=instance)
    return render(request, "catalog/category_form.html", {"form": form, "category": instance})


@login_required
def category_delete(request: HttpRequest, pk: int) -> HttpResponse:
    category = get_object_or_404(ProductCategory, pk=pk)
    if request.method == "POST":
        category.delete()
        return redirect("catalog:categories")
    return render(request, "catalog/category_form.html", {"category": category, "delete": True})


@login_required
@require_POST
def category_reorder(request: HttpRequest) -> HttpResponse:
    """htmx/SortableJS: reassign ``ProductCategory.order`` from a list of ``category=<pk>`` (repeated)
    given in the new visual order."""
    ids = [int(x) for x in request.POST.getlist("category") if x.isdigit()]
    known = set(ProductCategory.objects.filter(pk__in=ids).values_list("pk", flat=True))
    for idx, pk in enumerate(i for i in ids if i in known):
        ProductCategory.objects.filter(pk=pk).update(order=idx)
    from django.http import JsonResponse

    return JsonResponse({"ok": True})


# --- Public, login-free showroom (tenant resolved from the URL slug) ---------
def _public_tenant(tenant_slug: str):
    from apps.tenants.models import Tenant

    return get_object_or_404(Tenant, slug=tenant_slug, is_active=True)


_PRICE_BANDS = {
    "u5000": (None, 5000),
    "5to15": (5000, 15000),
    "15to50": (15000, 50000),
    "o50000": (50000, None),
}


def public_catalog(request: HttpRequest, tenant_slug: str) -> HttpResponse:
    """Browse the tenant's published catalog with keyword + category + price-band filters.
    Filter UI is htmx-friendly (just query params today; the page rerenders cheaply)."""
    tenant = _public_tenant(tenant_slug)
    selected_cat = request.GET.get("cat", "").strip() or request.GET.get("category", "").strip()
    q = (request.GET.get("q") or "").strip()[:120]
    band = (request.GET.get("price") or "").strip()
    with tenant_context(tenant):
        from apps.tenants.models import CompanyProfile

        categories = list(
            ProductCategory.objects.annotate(
                n=Count("products", filter=Q(products__is_active=True))
            )
            .filter(n__gt=0)
            .order_by("order", "name")
        )
        products = (
            Product.objects.filter(is_active=True)
            .select_related("category")
            .order_by("category__order", "name")
        )
        if selected_cat.isdigit():
            products = products.filter(category_id=int(selected_cat))
        if q:
            products = products.filter(Q(name__icontains=q) | Q(code__icontains=q))
        if band in _PRICE_BANDS:
            lo, hi = _PRICE_BANDS[band]
            if lo is not None:
                products = products.filter(default_price__gte=lo)
            if hi is not None:
                products = products.filter(default_price__lte=hi)
        return render(
            request,
            "catalog/public_catalog.html",
            {
                "tenant": tenant,
                "company": CompanyProfile.objects.filter(tenant=tenant).first(),
                "categories": categories,
                "products": list(products),
                "selected_cat": selected_cat,
                "q": q,
                "price_band": band,
            },
        )


def public_home(request: HttpRequest, tenant_slug: str | None = None, tenant=None) -> HttpResponse:
    """Per-tenant public landing page (deck "หน้าหลักสาธารณะ"): hero, browse-by-category,
    featured products, an AI-match teaser, how-it-works, contact footer."""
    if tenant is None:
        tenant = _public_tenant(tenant_slug or "")
    with tenant_context(tenant):
        from apps.integrations.ai import ai_is_configured
        from apps.tenants.models import CompanyProfile

        company = CompanyProfile.objects.filter(tenant=tenant).first()
        categories = list(
            ProductCategory.objects.annotate(
                n=Count("products", filter=Q(products__is_active=True))
            )
            .filter(n__gt=0)
            .order_by("order", "name")[:8]
        )
        featured = list(
            Product.objects.filter(is_active=True)
            .select_related("category")
            .order_by("-created_at")[:8]
        )
        return render(
            request,
            "catalog/public_home.html",
            {
                "tenant": tenant,
                "company": company,
                "categories": categories,
                "featured": featured,
                "ai_enabled": ai_is_configured(),
            },
        )


def public_product(request: HttpRequest, tenant_slug: str, pk: int) -> HttpResponse:
    tenant = _public_tenant(tenant_slug)
    with tenant_context(tenant):
        from apps.tenants.models import CompanyProfile

        product = get_object_or_404(
            Product.objects.select_related("category").prefetch_related(
                "images", "variants", "options"
            ),
            pk=pk,
            is_active=True,
        )
        related = []
        if product.category_id:
            related = list(
                Product.objects.filter(is_active=True, category_id=product.category_id)
                .exclude(pk=product.pk)
                .select_related("category")
                .order_by("-created_at")[:4]
            )
        return render(
            request,
            "catalog/public_product.html",
            {
                "tenant": tenant,
                "company": CompanyProfile.objects.filter(tenant=tenant).first(),
                "product": product,
                "related_products": related,
            },
        )


def public_search(request: HttpRequest, tenant_slug: str) -> HttpResponse:
    """Public search · groups results by category (frame h)."""
    tenant = _public_tenant(tenant_slug)
    q = (request.GET.get("q") or "").strip()[:120]
    with tenant_context(tenant):
        from apps.tenants.models import CompanyProfile

        company = CompanyProfile.objects.filter(tenant=tenant).first()
        sections: list[dict] = []
        total = 0
        if q:
            hits = list(
                Product.objects.filter(is_active=True)
                .filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(description__icontains=q))
                .select_related("category")
                .order_by("category__order", "name")[:60]
            )
            total = len(hits)
            by_cat: dict[int | None, list] = {}
            for p in hits:
                by_cat.setdefault(p.category_id, []).append(p)
            cat_objs = {
                c.pk: c
                for c in ProductCategory.objects.filter(pk__in=[k for k in by_cat if k is not None])
            }
            for cat_id, items in by_cat.items():
                sections.append(
                    {
                        "category": cat_objs.get(cat_id) if cat_id is not None else None,
                        "items": items[:6],
                        "more": max(0, len(items) - 6),
                    }
                )
        return render(
            request,
            "catalog/public_search.html",
            {"tenant": tenant, "company": company, "q": q, "sections": sections, "total": total},
        )


def public_quote_request(request: HttpRequest, tenant_slug: str) -> HttpResponse:
    """Public Path A endpoint · GET shows the form, POST creates a quote request.
    No login required. Rate-limited per-IP via the cache backend (5/hr soft cap)."""
    tenant = _public_tenant(tenant_slug)
    with tenant_context(tenant):
        from apps.crm.models import Contact, Customer
        from apps.quotes.models import DocSource, DocStatus, DocType, SalesDocLine, SalesDocument
        from apps.tenants.models import CompanyProfile

        from .forms import QuoteRequestForm

        company = CompanyProfile.objects.filter(tenant=tenant).first()

        if request.method == "POST":
            # Tiny rate-limit · 5 submits per hour per IP. Caches keyed by IP only — fine for MVP.
            from django.core.cache import cache

            ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "?")
            cache_key = f"qr-submit:{tenant.slug}:{ip}"
            hits = cache.get(cache_key, 0)
            if hits >= 5:
                form = QuoteRequestForm(request.POST)
                return render(
                    request,
                    "catalog/quote_request.html",
                    {"tenant": tenant, "company": company, "form": form, "throttled": True},
                )
            cache.set(cache_key, hits + 1, timeout=3600)

            form = QuoteRequestForm(request.POST)
            if form.is_valid():
                d = form.cleaned_data
                customer = Customer.objects.create(
                    name=d["company_name"] or d["name"],
                    shipping_address=d.get("address") or "",
                )
                Contact.objects.create(
                    customer=customer,
                    name=d["name"],
                    phone=d["phone"],
                    email=d["contact"] if "@" in d["contact"] else "",
                    line_id=d["contact"] if "@" not in d["contact"] else "",
                    is_primary=True,
                )
                from datetime import date as _date

                doc = SalesDocument.objects.create(
                    doc_type=DocType.QUOTATION,
                    status=DocStatus.REQUEST,
                    source=DocSource.WEBSITE,
                    customer=customer,
                    issue_date=_date.today(),
                    reference=(d.get("install_date") or "")[:200],
                    notes="\n".join(
                        filter(
                            None,
                            [
                                f"บริการ: {d['service']}" if d.get("service") else "",
                                f"ติดตั้ง: {d['install_date']}" if d.get("install_date") else "",
                                d.get("notes") or "",
                            ],
                        )
                    ),
                )
                # Translate cart entries → lines (best-effort: skip products that don't exist).
                cart = d.get("cart") or []
                positions = 0
                for item in cart:
                    p = Product.objects.filter(pk=item["id"], is_active=True).first()
                    if not p:
                        continue
                    positions += 1
                    SalesDocLine.objects.create(
                        document=doc,
                        position=positions,
                        product=p,
                        description=p.name,
                        quantity=item["qty"],
                        unit=p.unit or "",
                        unit_price=p.default_price or 0,
                    )
                return render(
                    request,
                    "catalog/quote_request_thanks.html",
                    {"tenant": tenant, "company": company, "ref": doc.doc_number or f"REQ-{doc.pk}", "doc": doc},
                )
        else:
            form = QuoteRequestForm()

        return render(
            request,
            "catalog/quote_request.html",
            {"tenant": tenant, "company": company, "form": form},
        )


@require_POST
def public_catalog_match(request: HttpRequest, tenant_slug: str) -> HttpResponse:
    """Public, login-free: visitor types what they want; if AI is configured we ask Claude to
    match the tenant's catalog and show the matched products. Degrades gracefully — never 500."""
    tenant = _public_tenant(tenant_slug)
    text = (request.POST.get("q") or "").strip()[:2000]
    with tenant_context(tenant):
        from apps.integrations.ai import (
            AINotConfigured,
            ai_is_configured,
            draft_quotation_from_text,
        )
        from apps.tenants.models import CompanyProfile

        company = CompanyProfile.objects.filter(tenant=tenant).first()
        ctx: dict = {"tenant": tenant, "company": company, "query": text}
        if not text:
            ctx["error"] = "พิมพ์สิ่งที่ต้องการก่อนนะ"
            return render(request, "catalog/_match_results.html", ctx)
        if not ai_is_configured():
            ctx["fallback"] = True
            return render(request, "catalog/_match_results.html", ctx)
        products = list(Product.objects.filter(is_active=True).select_related("category"))
        catalog = [
            {"code": p.code, "name": p.name, "unit": p.unit, "price": str(p.default_price)}
            for p in products
        ]
        from apps.tenants.quota import QuotaExceeded, gated

        try:
            with gated(tenant, "ai_drafts"):
                draft = draft_quotation_from_text(text, catalog=catalog)
        except QuotaExceeded:
            ctx["fallback"] = True
            ctx["ai_error"] = "ผู้ช่วยเอไอเต็มโควต้าเดือนนี้"
            return render(request, "catalog/_match_results.html", ctx)
        except AINotConfigured:
            ctx["fallback"] = True
            return render(request, "catalog/_match_results.html", ctx)
        except Exception as exc:  # noqa: BLE001 — degrade, don't 500
            ctx["fallback"] = True
            ctx["ai_error"] = str(exc)
            return render(request, "catalog/_match_results.html", ctx)
        by_code = {p.code: p for p in products if p.code}
        matches = []
        for line in draft.get("lines", []):
            code = (line.get("product_code") or "").strip()
            prod = by_code.get(code) if code else None
            matches.append({"product": prod, "description": line.get("description", "")})
        ctx["matches"] = matches
        ctx["notes"] = draft.get("notes", "")
        return render(request, "catalog/_match_results.html", ctx)
