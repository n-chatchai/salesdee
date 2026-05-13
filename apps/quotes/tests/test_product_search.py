"""Type-ahead product picker for the quote line editor."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def test_product_search_matches_name_and_code(client, user, membership, tenant) -> None:
    from apps.catalog.models import Product, TaxType

    with tenant_context(tenant):
        Product.objects.create(name="โต๊ะทำงาน", code="DESK-1", default_price=Decimal("6500"))
        Product.objects.create(name="เก้าอี้ทำงาน", code="CHAIR-1", default_price=Decimal("2200"))
        Product.objects.create(name="โซฟา 3 ที่นั่ง", code="SOF-3", default_price=Decimal("19000"))
        # inactive product is excluded
        Product.objects.create(
            name="โต๊ะข้างเตียง",
            code="DESK-OLD",
            default_price=Decimal("3500"),
            is_active=False,
            tax_type=TaxType.VAT7,
        )
    client.force_login(user)
    # match by name
    r = client.get(reverse("quotes:product_search") + "?q=โต๊ะ")
    assert r.status_code == 200
    assert b"DESK-1" in r.content
    assert b"DESK-OLD" not in r.content  # inactive excluded
    # match by code
    r = client.get(reverse("quotes:product_search") + "?q=CHAIR")
    assert b"CHAIR-1" in r.content
    assert b"DESK-1" not in r.content
    # empty query → no results, no 500
    r = client.get(reverse("quotes:product_search") + "?q=")
    assert r.status_code == 200
    assert b"DESK-1" not in r.content


def test_product_search_is_tenant_scoped(client, user, membership, tenant, other_tenant) -> None:
    from apps.catalog.models import Product

    with tenant_context(other_tenant):
        Product.objects.create(name="สินค้าของร้านอื่น", code="OTHER-1", default_price=Decimal("100"))
    with tenant_context(tenant):
        Product.objects.create(name="ของเรา", code="OURS-1", default_price=Decimal("200"))
    client.force_login(user)
    r = client.get(reverse("quotes:product_search") + "?q=สินค้า")
    # other tenant's product must not leak (current tenant resolves to `tenant` via membership)
    assert b"OTHER-1" not in r.content


def test_add_line_picker_appears_on_quote_detail(client, user, membership, tenant) -> None:
    """The type-ahead picker input is rendered in the add-line form on the quote detail page."""
    from apps.catalog.models import Product
    from apps.quotes.services import create_quotation_from_ai_draft

    with tenant_context(tenant):
        Product.objects.create(name="โต๊ะ", code="DK", default_price=Decimal("1000"))
        doc = create_quotation_from_ai_draft({"lines": []}, salesperson=user)
    client.force_login(user)
    page = client.get(reverse("quotes:quotation_detail", args=[doc.pk]))
    assert page.status_code == 200
    # the picker is present (id + hx endpoint)
    assert b"product-picker" in page.content
    assert b"product-search" in page.content
