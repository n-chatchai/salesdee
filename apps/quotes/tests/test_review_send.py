"""One-click "ตรวจแล้วส่งทาง LINE" flow — Quote-from-Chat review surface."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def test_conversation_make_quote_redirects_to_review(
    client, user, membership, tenant, monkeypatch
) -> None:
    """make-quote now lands on the focused review surface (one screen, one CTA)."""
    from apps.catalog.models import Product, TaxType
    from apps.integrations.line import _record_inbound_text
    from apps.integrations.models import Conversation

    with tenant_context(tenant):
        Product.objects.create(
            name="โต๊ะ", code="DK", default_price=Decimal("5000"), unit="ตัว", tax_type=TaxType.VAT7
        )
        _record_inbound_text("Ureview", "สนใจโต๊ะ 2 ตัว ขอใบเสนอราคาค่ะ")
        conv = Conversation.objects.get(external_id="Ureview")

    def fake_draft(conversation, *, catalog):
        return {
            "lines": [{"product_code": "DK", "description": "โต๊ะ", "quantity": 2, "unit_price": 0}]
        }

    monkeypatch.setattr("apps.integrations.ai.draft_quotation_from_text", fake_draft)
    client.force_login(user)
    resp = client.post(reverse("integrations:conversation_make_quote", args=[conv.pk]))
    assert resp.status_code == 302
    from apps.quotes.models import SalesDocument

    with tenant_context(tenant):
        doc = SalesDocument.objects.latest("created_at")
    assert resp.url == reverse("quotes:quotation_review", args=[doc.pk])
    # the review page itself renders
    page = client.get(resp.url)
    assert page.status_code == 200
    assert b"\xe0\xb8\x95\xe0\xb8\xa3\xe0\xb8\xa7\xe0\xb8\x88" in page.content  # "ตรวจ"


def test_one_click_review_send_line(client, user, membership, tenant, monkeypatch) -> None:
    """Click "ตรวจแล้วส่งทาง LINE" once: doc becomes SENT, a Flex is pushed, a share-link exists,
    the send is logged on the source thread, and an audit event is recorded."""
    from apps.audit.models import AuditEvent
    from apps.catalog.models import Product, TaxType
    from apps.integrations.models import (
        Conversation,
        LineIntegration,
        MessageDirection,
    )
    from apps.quotes.models import DocStatus, QuotationShareLink, SalesDocument
    from apps.quotes.services import create_quotation_from_ai_draft

    with tenant_context(tenant):
        LineIntegration.objects.create(channel_access_token="tok", channel_secret="sec")
        Product.objects.create(
            name="เก้าอี้",
            code="CH",
            default_price=Decimal("2000"),
            unit="ตัว",
            tax_type=TaxType.VAT7,
        )
        conv = Conversation.objects.create(external_id="Uone", display_name="คุณบี")
        doc = create_quotation_from_ai_draft(
            {"lines": [{"product_code": "CH", "description": "เก้าอี้", "quantity": 3}]},
            salesperson=user,
            reference="คุณบี",
        )
        doc.source_conversation = conv
        doc.save(update_fields=["source_conversation"])

    calls: list[dict] = []
    monkeypatch.setattr(
        "apps.integrations.line.push_quotation_flex",
        lambda to, **kw: calls.append({"to": to, **kw}),
    )
    client.force_login(user)
    resp = client.post(reverse("quotes:quotation_review_send_line", args=[doc.pk]))
    assert resp.status_code == 302
    # routes back to the source conversation (keeps user in the inbox flow)
    assert resp.url == reverse("integrations:conversation", args=[conv.pk])
    assert len(calls) == 1 and calls[0]["to"] == "Uone"
    with tenant_context(tenant):
        doc = SalesDocument.objects.get(pk=doc.pk)
        assert doc.status == DocStatus.SENT
        assert QuotationShareLink.objects.filter(document=doc).exists()
        assert conv.messages.filter(
            direction=MessageDirection.OUT, text__startswith="ส่งใบเสนอราคา"
        ).exists()
        assert AuditEvent.objects.filter(action="quotation.sent", object_id=doc.pk).exists()


def test_review_send_line_no_recipient(client, user, membership, tenant) -> None:
    """No LINE id and no source conversation → error message, no state change."""
    from apps.catalog.models import Product, TaxType
    from apps.quotes.models import DocStatus
    from apps.quotes.services import create_quotation_from_ai_draft

    with tenant_context(tenant):
        Product.objects.create(
            name="ตู้", code="CB", default_price=Decimal("9000"), unit="ใบ", tax_type=TaxType.VAT7
        )
        doc = create_quotation_from_ai_draft(
            {"lines": [{"product_code": "CB", "description": "ตู้", "quantity": 1}]},
            salesperson=user,
        )
    client.force_login(user)
    resp = client.post(reverse("quotes:quotation_review_send_line", args=[doc.pk]))
    assert resp.status_code == 302
    assert resp.url == reverse("quotes:quotation_review", args=[doc.pk])
    with tenant_context(tenant):
        doc.refresh_from_db()
        assert doc.status == DocStatus.DRAFT
