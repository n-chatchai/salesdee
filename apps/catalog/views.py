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


def _public_base_products():
    return (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .prefetch_related("images", "variants")
    )


def public_catalog(request: HttpRequest, tenant_slug: str) -> HttpResponse:
    """Browse catalog · deck frame b (facets, lead-time, sort)."""
    tenant = _public_tenant(tenant_slug)
    selected_cat = request.GET.get("cat", "").strip() or request.GET.get("category", "").strip()
    q = (request.GET.get("q") or "").strip()[:120]
    band = (request.GET.get("price") or "").strip()
    fast_only = request.GET.get("fast") == "1"
    sort = (request.GET.get("sort") or "default").strip()
    with tenant_context(tenant):
        from apps.catalog.public_site import (
            enrich_categories,
            facet_lead_time_counts,
            facet_price_counts,
        )
        from apps.tenants.models import CompanyProfile

        company = CompanyProfile.objects.filter(tenant=tenant).first()
        categories = list(
            ProductCategory.objects.annotate(
                n=Count("products", filter=Q(products__is_active=True))
            )
            .filter(n__gt=0)
            .order_by("order", "name")
        )
        cat_rows = enrich_categories(categories)
        base_qs = _public_base_products()
        facet_base = base_qs
        active_category = None
        if selected_cat.isdigit():
            active_category = ProductCategory.objects.filter(pk=int(selected_cat)).first()
            base_qs = base_qs.filter(category_id=int(selected_cat))
            facet_base = facet_base.filter(category_id=int(selected_cat))
        if q:
            base_qs = base_qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        if band in _PRICE_BANDS:
            lo, hi = _PRICE_BANDS[band]
            if lo is not None:
                base_qs = base_qs.filter(default_price__gte=lo)
            if hi is not None:
                base_qs = base_qs.filter(default_price__lte=hi)
        if fast_only:
            base_qs = base_qs.filter(lead_time_days__lte=7)
        if sort == "price_asc":
            base_qs = base_qs.order_by("default_price", "name")
        elif sort == "price_desc":
            base_qs = base_qs.order_by("-default_price", "name")
        elif sort == "fast":
            base_qs = base_qs.order_by("lead_time_days", "name")
        else:
            base_qs = base_qs.order_by("category__order", "name")
        products = list(base_qs)
        fast_count = facet_base.filter(lead_time_days__lte=7).count()
        return render(
            request,
            "catalog/public_catalog.html",
            {
                "tenant": tenant,
                "company": company,
                "categories": categories,
                "cat_rows": cat_rows,
                "nav_q": q,
                "products": products,
                "selected_cat": selected_cat,
                "active_category": active_category,
                "q": q,
                "price_band": band,
                "fast_only": fast_only,
                "fast_count": fast_count,
                "sort": sort,
                "facet_prices": facet_price_counts(facet_base),
                "facet_lead": facet_lead_time_counts(facet_base),
                "total_in_cat": facet_base.count(),
            },
        )


def public_home(request: HttpRequest, tenant_slug: str | None = None, tenant=None) -> HttpResponse:
    """Per-tenant landing · deck frame a."""
    if tenant is None:
        tenant = _public_tenant(tenant_slug or "")
    with tenant_context(tenant):
        from django.urls import reverse

        from apps.catalog.default_content import hero_slides_for_home
        from apps.catalog.models import PortfolioCase
        from apps.catalog.public_site import enrich_categories, facts_for_company
        from apps.integrations.ai import ai_is_configured
        from apps.tenants.models import CompanyProfile, HeroBanner

        company = CompanyProfile.objects.filter(tenant=tenant).first()
        banners = list(HeroBanner.objects.filter(is_active=True).order_by("order")[:4])
        hero_slides = hero_slides_for_home(banners, tenant, reverse)
        categories = list(
            ProductCategory.objects.annotate(
                n=Count("products", filter=Q(products__is_active=True))
            )
            .filter(n__gt=0)
            .order_by("order", "name")[:10]
        )
        cat_rows = enrich_categories(categories)
        product_count = Product.objects.filter(is_active=True).count()
        fast_qs = _public_base_products().filter(lead_time_days__lte=7)
        fast_count = fast_qs.count()
        fast_products = list(fast_qs.order_by("lead_time_days", "name")[:8])
        if not fast_products:
            fast_products = list(_public_base_products().order_by("-created_at")[:8])
        cases = list(PortfolioCase.objects.filter(is_active=True).order_by("order")[:4])
        return render(
            request,
            "catalog/public_home.html",
            {
                "tenant": tenant,
                "company": company,
                "cat_rows": cat_rows,
                "hero_slides": hero_slides,
                "fast_products": fast_products,
                "fast_count": fast_count,
                "category_count": len(categories),
                "product_count": product_count,
                "facts": facts_for_company(company, product_count=product_count),
                "cases": cases,
                "ai_enabled": ai_is_configured(),
            },
        )


def public_product(request: HttpRequest, tenant_slug: str, pk: int) -> HttpResponse:
    tenant = _public_tenant(tenant_slug)
    with tenant_context(tenant):
        from apps.catalog.models import PortfolioCase
        from apps.catalog.public_site import (
            format_price_range,
            lead_time_label,
            product_price_range,
        )
        from apps.tenants.models import CompanyProfile

        product = get_object_or_404(
            Product.objects.select_related("category").prefetch_related(
                "images", "variants", "options"
            ),
            pk=pk,
            is_active=True,
        )
        lo, hi = product_price_range(product)
        lead_text, lead_cls = lead_time_label(product.lead_time_days)
        related = []
        if product.category_id:
            related = list(
                _public_base_products()
                .filter(category_id=product.category_id)
                .exclude(pk=product.pk)
                .order_by("-created_at")[:4]
            )
        cases = list(PortfolioCase.objects.filter(is_active=True).order_by("order")[:3])
        return render(
            request,
            "catalog/public_product.html",
            {
                "tenant": tenant,
                "company": CompanyProfile.objects.filter(tenant=tenant).first(),
                "product": product,
                "price_range_text": format_price_range(lo, hi),
                "lead_text": lead_text,
                "lead_cls": lead_cls,
                "related_products": related,
                "cases": cases,
            },
        )


def public_compare(request: HttpRequest, tenant_slug: str) -> HttpResponse:
    tenant = _public_tenant(tenant_slug)
    raw = (request.GET.get("ids") or "").strip()
    ids = [int(x) for x in raw.split(",") if x.isdigit()][:4]
    with tenant_context(tenant):
        from apps.catalog.public_site import (
            format_price_range,
            lead_time_label,
            product_price_range,
        )
        from apps.tenants.models import CompanyProfile

        products = list(_public_base_products().filter(pk__in=ids))
        rows = []
        for label, fn in (
            ("ราคา", lambda p: format_price_range(*product_price_range(p))),
            ("ลีดไทม์", lambda p: lead_time_label(p.lead_time_days)[0]),
            ("วัสดุ", lambda p: p.material or "—"),
            ("ขนาด", lambda p: p.dimensions or "—"),
        ):
            rows.append({"label": label, "values": [fn(p) for p in products]})
        return render(
            request,
            "catalog/public_compare.html",
            {
                "tenant": tenant,
                "company": CompanyProfile.objects.filter(tenant=tenant).first(),
                "products": products,
                "rows": rows,
            },
        )


def public_showroom(request: HttpRequest, tenant_slug: str) -> HttpResponse:
    tenant = _public_tenant(tenant_slug)
    with tenant_context(tenant):
        from apps.tenants.models import CompanyProfile

        company = CompanyProfile.objects.filter(tenant=tenant).first()
        if request.method == "POST":
            from apps.crm.models import Activity, Customer

            name = (request.POST.get("name") or "").strip()[:200]
            phone = (request.POST.get("phone") or "").strip()[:40]
            when = (request.POST.get("visit_date") or "").strip()[:100]
            notes = (request.POST.get("notes") or "").strip()[:2000]
            if name and phone:
                customer = Customer.objects.create(name=name)
                from apps.crm.models import ActivityKind

                Activity.objects.create(
                    customer=customer,
                    kind=ActivityKind.MEETING,
                    body="นัด showroom (เว็บ)\n"
                    + "\n".join(filter(None, [f"เวลา: {when}" if when else "", notes])),
                )
                return render(
                    request,
                    "catalog/public_showroom_thanks.html",
                    {"tenant": tenant, "company": company},
                )
        return render(
            request,
            "catalog/public_showroom.html",
            {"tenant": tenant, "company": company},
        )


def public_bulk_request(request: HttpRequest, tenant_slug: str) -> HttpResponse:
    tenant = _public_tenant(tenant_slug)
    with tenant_context(tenant):
        from apps.tenants.models import CompanyProfile

        company = CompanyProfile.objects.filter(tenant=tenant).first()
        if request.method == "POST":
            from apps.crm.models import Activity, Customer

            name = (request.POST.get("name") or "").strip()[:200]
            phone = (request.POST.get("phone") or "").strip()[:40]
            budget = (request.POST.get("budget") or "").strip()[:100]
            people = (request.POST.get("people") or "").strip()[:50]
            notes = (request.POST.get("notes") or "").strip()[:2000]
            if name and phone:
                customer = Customer.objects.create(name=name)
                from apps.crm.models import ActivityKind

                Activity.objects.create(
                    customer=customer,
                    kind=ActivityKind.NOTE,
                    body="Bulk request (เว็บ)\n"
                    + "\n".join(
                        filter(
                            None,
                            [
                                f"งบ: {budget}" if budget else "",
                                f"จำนวนคน: {people}" if people else "",
                                notes,
                            ],
                        )
                    ),
                )
                return render(
                    request,
                    "catalog/public_bulk_thanks.html",
                    {"tenant": tenant, "company": company},
                )
        return render(
            request,
            "catalog/public_bulk.html",
            {"tenant": tenant, "company": company},
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

            ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
                0
            ].strip() or request.META.get("REMOTE_ADDR", "?")
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
                    {
                        "tenant": tenant,
                        "company": company,
                        "ref": doc.doc_number or f"REQ-{doc.pk}",
                        "doc": doc,
                    },
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
