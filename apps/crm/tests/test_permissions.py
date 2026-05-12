from __future__ import annotations

from datetime import date

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def _other_rep(tenant):
    from django.contrib.auth import get_user_model

    from apps.accounts.models import Membership, Role

    u = get_user_model().objects.create_user(
        email="rep2@example.test", password="testpass-12345", full_name="เซลส์ คนที่สอง"
    )
    Membership.objects.create(user=u, tenant=tenant, role=Role.SALES)
    return u


def test_restricted_rep_sees_only_own_records(client, user, membership, tenant) -> None:
    from apps.crm.models import Deal, DealStatus, Lead
    from apps.quotes.models import DocStatus, DocType, SalesDocument

    rep2 = _other_rep(tenant)
    membership.can_see_all_records = False
    membership.save()
    with tenant_context(tenant):
        my_deal = Deal.objects.create(name="ดีลของฉัน", owner=user, status=DealStatus.OPEN)
        their_deal = Deal.objects.create(name="ดีลคนอื่น", owner=rep2, status=DealStatus.OPEN)
        my_lead = Lead.objects.create(name="ลีดของฉัน", assigned_to=user)
        their_lead = Lead.objects.create(name="ลีดคนอื่น", assigned_to=rep2)
        my_q = SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            issue_date=date.today(),
            salesperson=user,
            doc_number="QT-MINE",
            status=DocStatus.DRAFT,
        )
        their_q = SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            issue_date=date.today(),
            salesperson=rep2,
            doc_number="QT-THEIR",
            status=DocStatus.DRAFT,
        )
    client.force_login(user)
    assert client.get(reverse("crm:deal_detail", args=[my_deal.pk])).status_code == 200
    assert client.get(reverse("crm:deal_detail", args=[their_deal.pk])).status_code == 404
    assert client.get(reverse("crm:lead_detail", args=[my_lead.pk])).status_code == 200
    assert client.get(reverse("crm:lead_detail", args=[their_lead.pk])).status_code == 404
    assert client.get(reverse("quotes:quotation_detail", args=[my_q.pk])).status_code == 200
    assert client.get(reverse("quotes:quotation_detail", args=[their_q.pk])).status_code == 404
    leads_body = client.get(reverse("crm:leads")).content.decode()
    assert "ลีดของฉัน" in leads_body and "ลีดคนอื่น" not in leads_body
    quotes_body = client.get(reverse("quotes:quotations")).content.decode()
    assert "QT-MINE" in quotes_body and "QT-THEIR" not in quotes_body


def test_unrestricted_rep_sees_everyones_records(client, user, membership, tenant) -> None:
    # membership.can_see_all_records defaults to True
    from apps.crm.models import Deal, DealStatus

    rep2 = _other_rep(tenant)
    with tenant_context(tenant):
        their_deal = Deal.objects.create(name="ดีลคนอื่น", owner=rep2, status=DealStatus.OPEN)
    client.force_login(user)
    assert client.get(reverse("crm:deal_detail", args=[their_deal.pk])).status_code == 200
