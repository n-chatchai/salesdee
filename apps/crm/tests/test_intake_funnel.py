"""Showroom → intake funnel: CTA links carry the product, intake creates a lead with
``source = "showroom · product=…"``, and the manager-notify task fires."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def test_public_product_cta_carries_product_id(client, tenant) -> None:
    from apps.catalog.models import Product

    with tenant_context(tenant):
        product = Product.objects.create(
            name="โต๊ะประชุม 8 ที่นั่ง", code="MTG-8", default_price=Decimal("28000")
        )
    page = client.get(reverse("public_product", args=[tenant.slug, product.pk]))
    assert page.status_code == 200
    body = page.content.decode()
    assert f"product_id={product.pk}" in body
    # the sticky mobile bar is rendered
    assert "pub-mobile-bar" in body


def test_intake_prefills_product_from_id(client, tenant) -> None:
    from apps.catalog.models import Product

    with tenant_context(tenant):
        product = Product.objects.create(
            name="ตู้เก็บเอกสาร 4 ลิ้นชัก", code="CAB-4", default_price=Decimal("9500")
        )
    url = reverse("crm:lead_intake", args=[tenant.slug]) + f"?product_id={product.pk}"
    page = client.get(url)
    assert page.status_code == 200
    # the product name is rendered as the initial value of the product_interest field
    assert "ตู้เก็บเอกสาร 4 ลิ้นชัก" in page.content.decode()


def test_intake_submit_records_source_and_fires_notification(
    client, tenant, user, monkeypatch
) -> None:
    """Submitting the form creates the lead with ``source=showroom · product=<pk>`` and the
    notify-new-lead task runs (best-effort email to managers/owners)."""
    from apps.accounts.models import Membership, Role
    from apps.catalog.models import Product
    from apps.crm.models import Lead, LeadChannel

    with tenant_context(tenant):
        product = Product.objects.create(
            name="โซฟา 3 ที่นั่ง", code="SOF-3", default_price=Decimal("19000")
        )
        Membership.objects.create(user=user, tenant=tenant, role=Role.OWNER)

    sent: list[dict] = []

    def fake_send_mail(**kwargs):
        sent.append(kwargs)
        return 1

    monkeypatch.setattr("apps.core.notifications.send_mail", fake_send_mail)
    url = reverse("crm:lead_intake", args=[tenant.slug])
    resp = client.post(
        url,
        {
            "name": "คุณลูกค้า",
            "phone": "0812345678",
            "product_interest": product.name,
            "product_id": str(product.pk),
            "message": "ส่งใบเสนอราคาให้หน่อยค่ะ",
        },
    )
    assert resp.status_code == 200
    with tenant_context(tenant):
        lead = Lead.objects.get(name="คุณลูกค้า")
        assert lead.channel == LeadChannel.WEB_FORM
        assert lead.source == f"showroom · product={product.pk}"
    # the manager email fired
    assert any(user.email in (m.get("recipient_list") or []) for m in sent)


def test_public_home_cta_link(client, tenant) -> None:
    page = client.get(reverse("public_home", args=[tenant.slug]))
    body = page.content.decode()
    # the hero now CTAs to lead_intake (the new conversion path)
    assert reverse("crm:lead_intake", args=[tenant.slug]) in body
