from __future__ import annotations

from datetime import date

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def test_search_finds_customer(client, user, membership, tenant) -> None:
    from apps.crm.models import Customer

    with tenant_context(tenant):
        Customer.objects.create(name="บริษัท เฟอร์นิเจอร์ดี จำกัด", billing_address="")
    client.force_login(user)
    resp = client.get(reverse("core:search"), {"q": "เฟอร์นิเจอร์ดี"})
    assert resp.status_code == 200
    assert "เฟอร์นิเจอร์ดี" in resp.content.decode()


def test_search_empty_query(client, user, membership, tenant) -> None:
    client.force_login(user)
    resp = client.get(reverse("core:search"))
    assert resp.status_code == 200


def test_search_requires_login(client) -> None:
    assert client.get(reverse("core:search")).status_code == 302


def test_notifications_renders_with_item(client, user, membership, tenant) -> None:
    from apps.quotes.models import DocStatus, DocType, SalesDocument

    with tenant_context(tenant):
        SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            issue_date=date.today(),
            status=DocStatus.SENT,
            doc_number="QT-NOTIF-1",
            salesperson=user,
        )
    client.force_login(user)
    resp = client.get(reverse("core:notifications"))
    assert resp.status_code == 200
    assert "QT-NOTIF-1" in resp.content.decode()


def test_notifications_requires_login(client) -> None:
    assert client.get(reverse("core:notifications")).status_code == 302
