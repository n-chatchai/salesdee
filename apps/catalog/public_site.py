"""Helpers for the per-tenant public buyer site (design/tenant-site.html)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db.models import Count, Max, Min, Q, QuerySet

if TYPE_CHECKING:
    from apps.catalog.models import Product, ProductCategory
    from apps.tenants.models import CompanyProfile


def brand_initials(name: str, *, max_len: int = 3) -> str:
    parts = [p for p in name.replace(".", " ").split() if p.strip()]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:max_len]
    return "".join(p[0] for p in parts[:max_len])


def lead_time_label(days: int | None) -> tuple[str, str]:
    """Return (display text, css class suffix: 'in' or 'mto')."""
    if days is None:
        return ("สอบถามลีดไทม์", "mto")
    if days <= 7:
        return (f"ส่ง {days} วัน" if days > 1 else "ส่ง 1 วัน", "in")
    if days <= 14:
        return (f"ส่ง {days} วัน", "in")
    weeks = max(1, (days + 6) // 7)
    return (f"สั่งทำ {weeks} สัปดาห์", "mto")


def product_price_range(product: Product) -> tuple[Decimal, Decimal]:

    prices = [product.default_price or Decimal(0)]
    for v in product.variants.filter(is_active=True):
        if v.price is not None:
            prices.append(v.price)
    lo, hi = min(prices), max(prices)
    return lo, hi


def format_price_range(lo: Decimal, hi: Decimal) -> str:
    lo_i, hi_i = int(lo), int(hi)
    if lo_i == hi_i:
        return f"฿{lo_i:,}"
    return f"฿{lo_i:,} — {hi_i:,}"


def format_price_compact(amount: Decimal | int) -> str:
    """Deck-style compact prices on category tiles (e.g. ฿2.4K)."""
    n = int(amount)
    if n >= 1_000_000:
        return f"฿{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1000:
        return f"฿{n / 1000:.1f}K".replace(".0K", "K")
    return f"฿{n:,}"


_CARD_GRADIENTS = (
    "linear-gradient(135deg, #4A4A4A 0%, #1A1A1A 100%)",
    "linear-gradient(135deg, #8B7355 0%, #4A3C2C 100%)",
    "linear-gradient(135deg, #5A5A5A 0%, #2A2A2A 100%)",
    "linear-gradient(135deg, #3A3A3A 0%, #1A1A1A 100%)",
    "linear-gradient(135deg, #C9B79A 0%, #8B7553 100%)",
    "linear-gradient(135deg, #C8B89A 0%, #8B7B5C 100%)",
    "linear-gradient(135deg, #A8B89A 0%, #687853 100%)",
    "linear-gradient(135deg, #B8A890 0%, #786853 100%)",
)


def product_card_gradient(product: Product) -> str:
    idx = (product.pk or 0) % len(_CARD_GRADIENTS)
    return _CARD_GRADIENTS[idx]


def category_fast_label(category: ProductCategory) -> str:
    from apps.catalog.models import Product

    min_days = (
        Product.objects.filter(is_active=True, category=category, lead_time_days__isnull=False)
        .aggregate(m=Min("lead_time_days"))
        .get("m")
    )
    if min_days is None:
        return ""
    return f"ส่ง {min_days} วัน+"


def category_stats(category: ProductCategory) -> dict[str, Any]:
    from apps.catalog.models import Product

    qs = Product.objects.filter(is_active=True, category=category)
    agg = qs.aggregate(
        n=Count("id"),
        price_min=Min("default_price"),
        price_max=Max("default_price"),
        fast=Count("id", filter=Q(lead_time_days__lte=7)),
    )
    return {
        "n": agg["n"] or 0,
        "price_min": agg["price_min"],
        "price_max": agg["price_max"],
        "fast": agg["fast"] or 0,
    }


def enrich_categories(categories: list[ProductCategory]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in categories:
        st = category_stats(c)
        price_range = ""
        if st["price_min"] is not None and st["price_max"] is not None:
            lo = format_price_compact(st["price_min"])
            hi = format_price_compact(st["price_max"])
            price_range = lo if lo == hi else f"{lo} — {hi}"
        out.append(
            {
                "category": c,
                "stats": st,
                "price_range": price_range,
                "fast_label": category_fast_label(c),
            }
        )
    return out


def facts_for_company(
    company: CompanyProfile | None, *, product_count: int
) -> list[dict[str, str]]:
    sku = (
        company.public_sku_count if company and company.public_sku_count else None
    ) or product_count
    sla = (company.public_response_sla_hours if company else None) or 24
    install_min = (company.public_free_install_min_thb if company else None) or 50000
    certs = (company.public_certifications if company else "") or "มอก. · ISO"
    install_k = f"{install_min // 1000}K" if install_min >= 1000 else str(install_min)
    return [
        {"num": f"{sku:,}+", "lbl": "รุ่นในแคตตาล็อก"},
        {"num": f"{sla} ชม.", "lbl": "ตอบใบเสนอราคา"},
        {"num": f"≥ ฿{install_k}", "lbl": "ติดตั้งฟรี กทม."},
        {"num": certs, "lbl": "มาตรฐาน/ใบรับรอง"},
    ]


def facet_price_counts(products: QuerySet[Product]) -> list[dict[str, Any]]:
    bands = [
        ("u5000", "ต่ำกว่า ฿5,000", None, 5000),
        ("5to15", "฿5,000–15,000", 5000, 15000),
        ("15to50", "฿15,000–25,000", 15000, 50000),
        ("o50000", "มากกว่า ฿25,000", 50000, None),
    ]
    out: list[dict[str, Any]] = []
    for key, label, lo, hi in bands:
        q = products
        if lo is not None:
            q = q.filter(default_price__gte=lo)
        if hi is not None:
            q = q.filter(default_price__lte=hi)
        out.append({"key": key, "label": label, "count": q.count()})
    return out


def facet_lead_time_counts(products: QuerySet[Product]) -> list[dict[str, Any]]:
    return [
        {
            "key": "fast5",
            "label": "≤ 5 วัน",
            "count": products.filter(lead_time_days__lte=5).count(),
        },
        {
            "key": "mid14",
            "label": "5–14 วัน",
            "count": products.filter(lead_time_days__gt=5, lead_time_days__lte=14).count(),
        },
        {
            "key": "mto",
            "label": "สั่งทำ 4–6 สัปดาห์",
            "count": products.filter(lead_time_days__gt=14).count(),
        },
    ]
