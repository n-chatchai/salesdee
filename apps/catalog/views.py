from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProductForm
from .models import Product


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
