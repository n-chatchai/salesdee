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


# --- Public, login-free showroom (tenant resolved from the URL slug) ---------
def _public_tenant(tenant_slug: str):
    from apps.tenants.models import Tenant

    return get_object_or_404(Tenant, slug=tenant_slug, is_active=True)


def public_catalog(request: HttpRequest, tenant_slug: str) -> HttpResponse:
    tenant = _public_tenant(tenant_slug)
    selected = request.GET.get("cat", "").strip()
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
        if selected.isdigit():
            products = products.filter(category_id=int(selected))
        return render(
            request,
            "catalog/public_catalog.html",
            {
                "tenant": tenant,
                "company": CompanyProfile.objects.filter(tenant=tenant).first(),
                "categories": categories,
                "products": list(products),
                "selected_cat": selected,
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
        return render(
            request,
            "catalog/public_product.html",
            {
                "tenant": tenant,
                "company": CompanyProfile.objects.filter(tenant=tenant).first(),
                "product": product,
            },
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
        try:
            draft = draft_quotation_from_text(text, catalog=catalog)
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
