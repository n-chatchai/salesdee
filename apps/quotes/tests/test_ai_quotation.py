from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def _lead_with_chat(tenant):
    from apps.crm.models import Activity, ActivityKind, Lead

    with tenant_context(tenant):
        lead = Lead.objects.create(name="บริษัท เอบีซี จำกัด", message="สนใจโต๊ะทำงาน 3 ตัวครับ")
        Activity.objects.create(
            lead=lead, kind=ActivityKind.LINE, body="ขอใบเสนอราคาด้วยนะครับ ส่งภายใน 30 วัน"
        )
        return lead


def test_create_quotation_from_ai_draft_service(tenant) -> None:
    from apps.catalog.models import Product, TaxType
    from apps.quotes.models import DocStatus, LineType
    from apps.quotes.services import create_quotation_from_ai_draft

    with tenant_context(tenant):
        Product.objects.create(
            name="โต๊ะ X",
            code="TBL-X",
            default_price=Decimal("8000"),
            unit="ตัว",
            tax_type=TaxType.VAT7,
        )
        draft = {
            "customer_name": "บ.เอบีซี",
            "notes": "ส่งภายใน 30 วัน",
            "lines": [
                {"product_code": "TBL-X", "description": "", "quantity": 3, "unit_price": 0},
                {"product_code": "", "description": "ค่าติดตั้ง", "quantity": 1, "unit_price": 5000},
            ],
        }
        doc = create_quotation_from_ai_draft(draft, reference="บริษัท เอบีซี")
        assert doc.status == DocStatus.DRAFT
        assert doc.doc_number.startswith("QT-")
        assert doc.reference == "บริษัท เอบีซี"
        assert doc.notes == "ส่งภายใน 30 วัน"
        lines = list(doc.lines.order_by("position"))
        assert len(lines) == 2
        assert lines[0].product is not None and lines[0].product.code == "TBL-X"
        assert lines[0].quantity == Decimal("3")
        assert lines[0].unit_price == Decimal("8000")  # filled from the catalog (AI gave 0)
        assert lines[0].line_type == LineType.ITEM
        assert lines[1].product is None
        assert lines[1].description == "ค่าติดตั้ง"
        assert lines[1].unit_price == Decimal("5000")


def test_quotation_from_lead_ai_view(client, user, membership, tenant, monkeypatch) -> None:
    from apps.catalog.models import Product, TaxType
    from apps.quotes.models import SalesDocument

    with tenant_context(tenant):
        Product.objects.create(
            name="โต๊ะทำงาน",
            code="DESK-1",
            default_price=Decimal("6500"),
            unit="ตัว",
            tax_type=TaxType.VAT7,
        )
    lead = _lead_with_chat(tenant)

    def fake_draft(conversation, *, catalog):
        assert "โต๊ะทำงาน" in conversation or "ใบเสนอราคา" in conversation
        return {
            "customer_name": "เอบีซี",
            "notes": "ส่งภายใน 30 วัน",
            "lines": [
                {
                    "product_code": "DESK-1",
                    "description": "โต๊ะทำงาน",
                    "quantity": 3,
                    "unit_price": 0,
                }
            ],
        }

    monkeypatch.setattr("apps.integrations.ai.draft_quotation_from_text", fake_draft)
    client.force_login(user)
    resp = client.post(reverse("quotes:quotation_from_lead_ai", args=[lead.pk]))
    assert resp.status_code == 302
    with tenant_context(tenant):
        doc = SalesDocument.objects.latest("created_at")
        assert resp.url == reverse("quotes:quotation_review", args=[doc.pk])
        assert doc.salesperson_id == user.pk
        assert doc.notes == "ส่งภายใน 30 วัน"
        line = doc.lines.get()
        assert line.product is not None and line.product.code == "DESK-1"
        assert line.quantity == Decimal("3")
        assert line.unit_price == Decimal("6500")


def test_quotation_from_lead_ai_no_conversation(client, user, membership, tenant) -> None:
    from apps.crm.models import Lead
    from apps.quotes.models import SalesDocument

    with tenant_context(tenant):
        lead = Lead.objects.create(name="ลีดเงียบ")
    client.force_login(user)
    resp = client.post(reverse("quotes:quotation_from_lead_ai", args=[lead.pk]))
    assert resp.status_code == 302
    assert resp.url == reverse("crm:lead_detail", args=[lead.pk])
    with tenant_context(tenant):
        assert not SalesDocument.objects.exists()


def test_quotation_from_lead_ai_without_api_key(client, user, membership, tenant, settings) -> None:
    from apps.quotes.models import SalesDocument

    settings.ANTHROPIC_API_KEY = ""  # the default in dev settings, but be explicit
    lead = _lead_with_chat(tenant)
    client.force_login(user)
    resp = client.post(reverse("quotes:quotation_from_lead_ai", args=[lead.pk]))
    assert resp.status_code == 302
    assert resp.url == reverse("crm:lead_detail", args=[lead.pk])
    with tenant_context(tenant):
        assert not SalesDocument.objects.exists()


def test_ai_button_visibility_on_lead_detail(client, user, membership, tenant, settings) -> None:
    lead = _lead_with_chat(tenant)
    client.force_login(user)
    settings.ANTHROPIC_API_KEY = ""
    assert (
        "ร่างใบเสนอราคาด้วย AI"
        not in client.get(reverse("crm:lead_detail", args=[lead.pk])).content.decode()
    )
    settings.ANTHROPIC_API_KEY = "test-key"
    assert (
        "ร่างใบเสนอราคาด้วย AI"
        in client.get(reverse("crm:lead_detail", args=[lead.pk])).content.decode()
    )
