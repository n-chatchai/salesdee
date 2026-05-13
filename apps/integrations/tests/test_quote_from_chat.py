from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context
from apps.integrations.line import _record_inbound_text
from apps.integrations.models import Conversation, MessageDirection

pytestmark = pytest.mark.django_db


def _conversation_with_chat(tenant):
    with tenant_context(tenant):
        _record_inbound_text("Ubuyer", "สนใจโต๊ะทำงาน 3 ตัว ขอใบเสนอราคาด้วยครับ")
        return Conversation.objects.get(external_id="Ubuyer")


def test_make_quote_from_conversation(client, user, membership, tenant, monkeypatch) -> None:
    from apps.catalog.models import Product, TaxType
    from apps.quotes.models import DocStatus, SalesDocument

    with tenant_context(tenant):
        Product.objects.create(
            name="โต๊ะทำงาน",
            code="DESK-1",
            default_price=Decimal("6500"),
            unit="ตัว",
            tax_type=TaxType.VAT7,
        )
    conv = _conversation_with_chat(tenant)

    def fake_draft(conversation, *, catalog):
        assert "โต๊ะทำงาน" in conversation
        return {
            "customer_name": "ผู้ซื้อ",
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
    resp = client.post(reverse("integrations:conversation_make_quote", args=[conv.pk]))
    assert resp.status_code == 302
    with tenant_context(tenant):
        doc = SalesDocument.objects.latest("created_at")
        assert resp.url == reverse("quotes:quotation_detail", args=[doc.pk])
        assert doc.status == DocStatus.DRAFT
        assert doc.source_conversation_id == conv.pk
        assert doc.salesperson_id == user.pk
        product = doc.lines.get().product
        assert product is not None and product.code == "DESK-1"


def test_make_quote_no_messages(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        # a bare conversation with no text messages
        conv = Conversation.objects.create(external_id="Uempty")
    client.force_login(user)
    resp = client.post(reverse("integrations:conversation_make_quote", args=[conv.pk]))
    assert resp.status_code == 302
    assert resp.url == reverse("integrations:conversation", args=[conv.pk])


def test_send_quotation_flex_to_source_conversation(
    client, user, membership, tenant, monkeypatch
) -> None:
    from apps.catalog.models import Product, TaxType
    from apps.quotes.models import DocStatus
    from apps.quotes.services import create_quotation_from_ai_draft

    with tenant_context(tenant):
        from apps.integrations.models import LineIntegration

        LineIntegration.objects.create(channel_access_token="tok", channel_secret="sec")
        Product.objects.create(
            name="เก้าอี้",
            code="CHR-1",
            default_price=Decimal("2500"),
            unit="ตัว",
            tax_type=TaxType.VAT7,
        )
        conv = Conversation.objects.create(external_id="Uflex", display_name="คุณเอ")
        doc = create_quotation_from_ai_draft(
            {
                "lines": [
                    {"product_code": "CHR-1", "description": "เก้าอี้", "quantity": 2, "unit_price": 0}
                ]
            },
            salesperson=user,
            reference="คุณเอ",
        )
        doc.source_conversation = conv
        doc.save(update_fields=["source_conversation"])

    calls: list[dict] = []

    def fake_flex(to, **kwargs):
        calls.append({"to": to, **kwargs})

    monkeypatch.setattr("apps.integrations.line.push_quotation_flex", fake_flex)
    client.force_login(user)
    resp = client.post(reverse("quotes:quotation_send_line", args=[doc.pk]))
    assert resp.status_code == 302
    assert len(calls) == 1
    assert calls[0]["to"] == "Uflex"
    assert "บาท" in calls[0]["total_text"]
    with tenant_context(tenant):
        doc.refresh_from_db()
        assert doc.status == DocStatus.SENT
        # the send is logged on the thread
        assert conv.messages.filter(
            direction=MessageDirection.OUT, text__startswith="ส่งใบเสนอราคา"
        ).exists()


def test_send_quotation_line_no_recipient(client, user, membership, tenant) -> None:
    from apps.catalog.models import Product, TaxType
    from apps.quotes.services import create_quotation_from_ai_draft

    with tenant_context(tenant):
        Product.objects.create(
            name="ตู้", code="CAB-1", default_price=Decimal("9000"), unit="ใบ", tax_type=TaxType.VAT7
        )
        doc = create_quotation_from_ai_draft(
            {
                "lines": [
                    {"product_code": "CAB-1", "description": "ตู้", "quantity": 1, "unit_price": 0}
                ]
            },
            salesperson=user,
        )
    client.force_login(user)
    resp = client.post(reverse("quotes:quotation_send_line", args=[doc.pk]))
    assert resp.status_code == 302
    assert resp.url == reverse("quotes:quotation_detail", args=[doc.pk])


def test_record_quote_viewed_counts(tenant) -> None:
    from apps.catalog.models import Product, TaxType
    from apps.quotes.services import create_quotation_from_ai_draft, record_quote_viewed

    with tenant_context(tenant):
        Product.objects.create(
            name="โซฟา",
            code="SOF-1",
            default_price=Decimal("15000"),
            unit="ตัว",
            tax_type=TaxType.VAT7,
        )
        doc = create_quotation_from_ai_draft(
            {
                "lines": [
                    {"product_code": "SOF-1", "description": "โซฟา", "quantity": 1, "unit_price": 0}
                ]
            }
        )
        record_quote_viewed(doc, ip="1.2.3.4")
        doc.refresh_from_db()
        assert doc.view_count == 1 and doc.first_viewed_at is not None
        first = doc.first_viewed_at
        record_quote_viewed(doc)
        doc.refresh_from_db()
        assert doc.view_count == 2 and doc.first_viewed_at == first
