from __future__ import annotations

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def _lead(tenant, **kwargs):
    from apps.crm.models import Lead

    with tenant_context(tenant):
        return Lead.objects.create(name="ลูกค้า ทดสอบ", message="สนใจโต๊ะทำงานครับ", **kwargs)


def test_lead_suggest_reply(client, user, membership, tenant, monkeypatch) -> None:
    lead = _lead(tenant)
    monkeypatch.setattr(
        "apps.integrations.ai.draft_reply_from_text",
        lambda conversation, *, company_name="": (
            "เรียนคุณลูกค้า ขอบคุณที่สนใจครับ ทางเรายินดีจัดทำใบเสนอราคาให้"
        ),
    )
    client.force_login(user)
    resp = client.post(reverse("crm:lead_suggest_reply", args=[lead.pk]))
    assert resp.status_code == 200
    assert "ยินดีจัดทำใบเสนอราคา" in resp.content.decode()


def test_lead_suggest_reply_no_conversation(client, user, membership, tenant) -> None:
    from apps.crm.models import Lead

    with tenant_context(tenant):
        lead = Lead.objects.create(name="ลีดเงียบ")
    client.force_login(user)
    resp = client.post(reverse("crm:lead_suggest_reply", args=[lead.pk]))
    assert resp.status_code == 200
    assert "ยังไม่มีบทสนทนา" in resp.content.decode()


def test_lead_send_line_reply(client, user, membership, tenant, monkeypatch) -> None:
    from apps.crm.models import Activity

    lead = _lead(tenant, line_id="Ulead123")
    sent: dict = {}
    monkeypatch.setattr(
        "apps.integrations.line.push_text", lambda to, text: sent.update(to=to, text=text)
    )
    client.force_login(user)
    resp = client.post(
        reverse("crm:lead_send_line_reply", args=[lead.pk]), {"text": "สวัสดีครับ จัดส่งภายใน 30 วัน"}
    )
    assert resp.status_code == 302
    assert resp.url == reverse("crm:lead_detail", args=[lead.pk])
    assert sent == {"to": "Ulead123", "text": "สวัสดีครับ จัดส่งภายใน 30 วัน"}
    with tenant_context(tenant):
        assert Activity.objects.filter(
            lead=lead, kind="line", body="สวัสดีครับ จัดส่งภายใน 30 วัน"
        ).exists()


def test_lead_send_line_reply_needs_text(client, user, membership, tenant, monkeypatch) -> None:
    lead = _lead(tenant, line_id="Ulead123")
    called = []
    monkeypatch.setattr(
        "apps.integrations.line.push_text", lambda to, text: called.append((to, text))
    )
    client.force_login(user)
    resp = client.post(reverse("crm:lead_send_line_reply", args=[lead.pk]), {"text": "  "})
    assert resp.status_code == 302
    assert called == []


def test_lead_suggest_reply_ai_not_configured(
    client, user, membership, tenant, monkeypatch
) -> None:
    from apps.integrations.ai import AINotConfigured

    lead = _lead(tenant)

    def _raise(conversation, *, company_name=""):
        raise AINotConfigured("ยังไม่ได้ตั้งค่า ANTHROPIC_API_KEY")

    monkeypatch.setattr("apps.integrations.ai.draft_reply_from_text", _raise)
    client.force_login(user)
    resp = client.post(reverse("crm:lead_suggest_reply", args=[lead.pk]))
    assert resp.status_code == 200
    assert "ANTHROPIC_API_KEY" in resp.content.decode()


def test_lead_send_line_reply_needs_line_id(client, user, membership, tenant, monkeypatch) -> None:
    lead = _lead(tenant)  # no line_id
    called = []
    monkeypatch.setattr(
        "apps.integrations.line.push_text", lambda to, text: called.append((to, text))
    )
    client.force_login(user)
    resp = client.post(reverse("crm:lead_send_line_reply", args=[lead.pk]), {"text": "สวัสดีครับ"})
    assert resp.status_code == 302
    assert resp.url == reverse("crm:lead_detail", args=[lead.pk])
    assert called == []


def test_lead_suggest_reply_api_error(client, user, membership, tenant, monkeypatch) -> None:
    lead = _lead(tenant)

    def _boom(conversation, *, company_name=""):
        raise RuntimeError("network down")

    monkeypatch.setattr("apps.integrations.ai.draft_reply_from_text", _boom)
    client.force_login(user)
    resp = client.post(reverse("crm:lead_suggest_reply", args=[lead.pk]))
    assert resp.status_code == 200
    assert "AI ร่างข้อความไม่สำเร็จ" in resp.content.decode()


def test_lead_suggest_reply_shows_send_line_when_configured(
    client, user, membership, tenant, monkeypatch
) -> None:
    from apps.integrations.models import LineIntegration
    from apps.tenants.models import CompanyProfile

    with tenant_context(tenant):
        LineIntegration.objects.create(channel_access_token="tok", is_active=True)
    CompanyProfile.objects.update_or_create(tenant=tenant, defaults={"name_th": "วัน.ดี.ดี."})
    lead = _lead(tenant, line_id="Ulead123")
    captured: dict = {}

    def _draft(conversation, *, company_name=""):
        captured["company_name"] = company_name
        return "เรียนคุณลูกค้า ยินดีเสนอราคาให้ครับ"

    monkeypatch.setattr("apps.integrations.ai.draft_reply_from_text", _draft)
    client.force_login(user)
    resp = client.post(reverse("crm:lead_suggest_reply", args=[lead.pk]))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "ส่งทาง LINE" in body
    assert captured["company_name"] == "วัน.ดี.ดี."


def test_lead_send_line_reply_line_not_configured(client, user, membership, tenant) -> None:
    lead = _lead(tenant, line_id="Ulead123")  # has a LINE id but no LineIntegration
    client.force_login(user)
    resp = client.post(reverse("crm:lead_send_line_reply", args=[lead.pk]), {"text": "สวัสดีครับ"})
    assert resp.status_code == 302
    with tenant_context(tenant):
        from apps.crm.models import Activity

        assert not Activity.objects.filter(lead=lead, kind="line").exists()


def test_lead_send_line_reply_sdk_error(client, user, membership, tenant, monkeypatch) -> None:
    lead = _lead(tenant, line_id="Ulead123")

    def _boom(to, text):
        raise RuntimeError("LINE API 500")

    monkeypatch.setattr("apps.integrations.line.push_text", _boom)
    client.force_login(user)
    resp = client.post(reverse("crm:lead_send_line_reply", args=[lead.pk]), {"text": "สวัสดีครับ"})
    assert resp.status_code == 302
    with tenant_context(tenant):
        from apps.crm.models import Activity

        assert not Activity.objects.filter(lead=lead, kind="line").exists()
