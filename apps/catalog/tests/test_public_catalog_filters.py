"""Public catalog: keyword + category + price-band filters narrow the queryset correctly."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded(tenant):
    from apps.catalog.models import Product, ProductCategory

    with tenant_context(tenant):
        cat_desk = ProductCategory.objects.create(name="โต๊ะ")
        cat_chair = ProductCategory.objects.create(name="เก้าอี้")
        Product.objects.create(
            name="โต๊ะทำงานเล็ก",
            code="DSK-S",
            default_price=Decimal("3500"),
            category=cat_desk,
        )
        Product.objects.create(
            name="โต๊ะทำงาน 1.5 ม.",
            code="DSK-M",
            default_price=Decimal("12000"),
            category=cat_desk,
        )
        Product.objects.create(
            name="โต๊ะประชุม 8 ที่นั่ง",
            code="DSK-L",
            default_price=Decimal("28000"),
            category=cat_desk,
        )
        Product.objects.create(
            name="เก้าอี้ทำงาน",
            code="CH-1",
            default_price=Decimal("4500"),
            category=cat_chair,
        )
    return tenant, cat_desk, cat_chair


def _names(html: str) -> set[str]:
    return {
        n for n in ("โต๊ะทำงานเล็ก", "โต๊ะทำงาน 1.5 ม.", "โต๊ะประชุม 8 ที่นั่ง", "เก้าอี้ทำงาน") if n in html
    }


def test_keyword_filter(client, seeded) -> None:
    tenant, _, _ = seeded
    page = client.get(reverse("public_catalog", args=[tenant.slug]) + "?q=ประชุม")
    assert page.status_code == 200
    assert _names(page.content.decode()) == {"โต๊ะประชุม 8 ที่นั่ง"}


def test_category_filter(client, seeded) -> None:
    tenant, cat_desk, _ = seeded
    page = client.get(reverse("public_catalog", args=[tenant.slug]) + f"?cat={cat_desk.pk}")
    names = _names(page.content.decode())
    assert "เก้าอี้ทำงาน" not in names
    assert {"โต๊ะทำงานเล็ก", "โต๊ะทำงาน 1.5 ม.", "โต๊ะประชุม 8 ที่นั่ง"} <= names


def test_price_band_filter(client, seeded) -> None:
    tenant, _, _ = seeded
    page = client.get(reverse("public_catalog", args=[tenant.slug]) + "?price=u5000")
    names = _names(page.content.decode())
    assert names == {"โต๊ะทำงานเล็ก", "เก้าอี้ทำงาน"}
    # 15k–50k narrows to the meeting table
    page = client.get(reverse("public_catalog", args=[tenant.slug]) + "?price=15to50")
    assert _names(page.content.decode()) == {"โต๊ะประชุม 8 ที่นั่ง"}


def test_combined_filters(client, seeded) -> None:
    tenant, cat_desk, _ = seeded
    page = client.get(
        reverse("public_catalog", args=[tenant.slug]) + f"?cat={cat_desk.pk}&price=5to15&q=โต๊ะ"
    )
    assert _names(page.content.decode()) == {"โต๊ะทำงาน 1.5 ม."}
