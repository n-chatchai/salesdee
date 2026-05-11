from __future__ import annotations

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context
from apps.crm.models import Customer, Deal, Lead, LeadChannel, LeadStatus

pytestmark = pytest.mark.django_db


def test_lead_create_manual(client, user, membership, tenant) -> None:
    client.force_login(user)
    resp = client.post(
        reverse("crm:lead_create"),
        {"name": "คุณสมชาย", "company_name": "บริษัท เอ จำกัด", "channel": "phone", "status": "new"},
    )
    assert resp.status_code == 302
    with tenant_context(tenant):
        lead = Lead.objects.get(name="คุณสมชาย")
        assert lead.company_name == "บริษัท เอ จำกัด"
        assert lead.channel == "phone"
    assert resp.url == reverse("crm:lead_detail", args=[lead.pk])


def test_lead_convert_creates_customer_and_deal(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        lead = Lead.objects.create(
            name="คุณวิภา", company_name="โรงเรียน บี", product_interest="ตู้ล็อกเกอร์ 20 ตู้", budget=80000
        )
    client.force_login(user)
    resp = client.post(reverse("crm:lead_convert", args=[lead.pk]))
    assert resp.status_code == 302
    with tenant_context(tenant):
        lead.refresh_from_db()
        assert lead.status == LeadStatus.CONVERTED
        assert lead.customer is not None and lead.deal is not None
        customer = Customer.objects.get(name="โรงเรียน บี")
        assert customer.contacts.filter(name="คุณวิภา").exists()
        deal = Deal.objects.get(name="ตู้ล็อกเกอร์ 20 ตู้")
        assert deal.customer_id == customer.pk
        assert deal.estimated_value == 80000
        assert deal.stage is not None
    assert resp.url == reverse("crm:deal_detail", args=[deal.pk])


def test_lead_convert_is_idempotent(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        lead = Lead.objects.create(name="คุณเอก")
    client.force_login(user)
    first = client.post(reverse("crm:lead_convert", args=[lead.pk]))
    second = client.post(reverse("crm:lead_convert", args=[lead.pk]))
    assert first.url == second.url
    with tenant_context(tenant):
        assert Deal.objects.count() == 1


def test_public_intake_creates_lead(client, tenant) -> None:
    url = reverse("crm:lead_intake", args=[tenant.slug])
    assert client.get(url).status_code == 200
    resp = client.post(
        url,
        {
            "name": "ลูกค้าจากเว็บ",
            "phone": "0812345678",
            "product_interest": "โต๊ะประชุม",
            "message": "ขอราคาด่วน",
        },
    )
    assert resp.status_code == 200
    assert "ขอบคุณ" in resp.content.decode()
    with tenant_context(tenant):
        lead = Lead.objects.get(name="ลูกค้าจากเว็บ")
        assert lead.channel == LeadChannel.WEB_FORM
        assert lead.status == LeadStatus.NEW


def test_public_intake_unknown_tenant_is_404(client) -> None:
    assert client.get(reverse("crm:lead_intake", args=["no-such-tenant"])).status_code == 404


def test_public_intake_lands_in_right_tenant(client, tenant, other_tenant) -> None:
    client.post(reverse("crm:lead_intake", args=[other_tenant.slug]), {"name": "เฉพาะของอีกบริษัท"})
    with tenant_context(tenant):
        assert not Lead.objects.filter(name="เฉพาะของอีกบริษัท").exists()
    with tenant_context(other_tenant):
        assert Lead.objects.filter(name="เฉพาะของอีกบริษัท").exists()
