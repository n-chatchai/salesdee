from __future__ import annotations

from django import template
from django.utils.safestring import mark_safe

from apps.catalog.public_site import (
    brand_initials,
    format_price_range,
    lead_time_label,
    product_card_gradient,
    product_price_range,
)

register = template.Library()


@register.filter
def ts_initials(name: str) -> str:
    return brand_initials(name or "")


@register.filter
def lead_time_text(product) -> str:
    return lead_time_label(getattr(product, "lead_time_days", None))[0]


@register.filter
def lead_time_class(product) -> str:
    return lead_time_label(getattr(product, "lead_time_days", None))[1]


@register.simple_tag
def ts_price_range(product) -> str:
    lo, hi = product_price_range(product)
    return format_price_range(lo, hi)


@register.filter
def brand_emphasis(name: str) -> str:
    """Deck-style brand lockup: wandee<em>dee</em>."""
    n = (name or "").strip()
    if len(n) <= 4:
        return n
    return mark_safe(f"{n[:-3]}<em>{n[-3:]}</em>")


@register.filter
def ts_card_gradient(product) -> str:
    return product_card_gradient(product)
