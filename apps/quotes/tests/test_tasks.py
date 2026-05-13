from __future__ import annotations

from datetime import date

import pytest

from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def test_send_quotation_via_line_task_pushes_and_logs(tenant, user, monkeypatch) -> None:
    from apps.catalog.models import Product, TaxType
    from apps.integrations.models import Conversation, LineIntegration, MessageDirection
    from apps.quotes.services import create_quotation_from_ai_draft
    from apps.quotes.tasks import send_quotation_via_line

    calls: list[dict] = []
    monkeypatch.setattr(
        "apps.integrations.line.push_quotation_flex",
        lambda to, **kw: calls.append({"to": to, **kw}),
    )
    with tenant_context(tenant):
        LineIntegration.objects.create(channel_access_token="tok")
        Product.objects.create(
            name="โต๊ะ", code="T-1", default_price="3000", unit="ตัว", tax_type=TaxType.VAT7
        )
        conv = Conversation.objects.create(external_id="Utask", display_name="คุณเอ")
        doc = create_quotation_from_ai_draft(
            {
                "lines": [
                    {"product_code": "T-1", "description": "โต๊ะ", "quantity": 1, "unit_price": 0}
                ]
            },
            salesperson=user,
        )

    send_quotation_via_line.enqueue(
        doc.pk,
        tenant.pk,
        recipient="Utask",
        doc_number="QT-1",
        customer_name="คุณเอ",
        total_text="3,210.00 บาท",
        valid_text="—",
        view_url="https://x/q/abc",
        pdf_url="https://x/q/abc/pdf",
        company_name="",
        log_to_conversation_id=conv.pk,
        sender_user_id=user.pk,
    )
    assert calls and calls[0]["to"] == "Utask"
    with tenant_context(tenant):
        conv.refresh_from_db()
        assert conv.messages.filter(
            direction=MessageDirection.OUT, text__startswith="ส่งใบเสนอราคา"
        ).exists()


def test_render_and_email_quotation_task(tenant, user, monkeypatch) -> None:
    from django.core import mail

    from apps.quotes.models import DocStatus, DocType, SalesDocument
    from apps.quotes.tasks import render_and_email_quotation

    monkeypatch.setattr("apps.quotes.pdf.render_quotation_pdf", lambda doc: b"%PDF-")
    with tenant_context(tenant):
        doc = SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            issue_date=date.today(),
            doc_number="QT-9",
            status=DocStatus.SENT,
        )
    render_and_email_quotation.enqueue(
        doc.pk,
        tenant.pk,
        recipient_email="c@example.com",
        recipient_name="คุณซี",
        public_url="https://x/q/zzz",
    )
    assert len(mail.outbox) == 1
    assert "https://x/q/zzz" in mail.outbox[0].body
