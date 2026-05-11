from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.current_tenant import tenant_context

from .forms import ProductForm
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
