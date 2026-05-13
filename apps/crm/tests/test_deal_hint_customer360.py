from __future__ import annotations

from datetime import date

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def test_deal_detail_shows_next_step_no_quotation(client, user, membership, tenant) -> None:
    from apps.crm.models import Deal

    with tenant_context(tenant):
        deal = Deal.objects.create(name="ดีลทดสอบ", owner=user)
    client.force_login(user)
    resp = client.get(reverse("crm:deal_detail", args=[deal.pk]))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "ขั้นถัดไปที่แนะนำ" in body
    assert "ยังไม่มีใบเสนอราคา" in body


def test_customer_detail_shows_quotation_views_and_conversations(
    client, user, membership, tenant
) -> None:
    from apps.crm.models import Customer
    from apps.integrations.models import Conversation
    from apps.quotes.models import DocStatus, DocType, SalesDocument

    with tenant_context(tenant):
        customer = Customer.objects.create(name="ลูกค้า 360", billing_address="")
        SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            issue_date=date.today(),
            status=DocStatus.SENT,
            doc_number="QT-360-1",
            customer=customer,
            salesperson=user,
            view_count=4,
        )
        Conversation.objects.create(external_id="U123", display_name="คุณเอ", customer=customer)
    client.force_login(user)
    resp = client.get(reverse("crm:customer_detail", args=[customer.pk]))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "QT-360-1" in body
    assert "ลูกค้าเปิด 4 ครั้ง" in body
    assert "คุณเอ" in body
