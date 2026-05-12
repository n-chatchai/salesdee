from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context
from apps.integrations.line import LineNotConfigured, line_is_configured, push_text
from apps.integrations.models import LineIntegration

pytestmark = pytest.mark.django_db


def _line_sig(secret: str, body: bytes) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def _text_event_body(user_id: str, text: str) -> bytes:
    return json.dumps(
        {
            "destination": "Ubot",
            "events": [
                {
                    "type": "message",
                    "mode": "active",
                    "timestamp": 1,
                    "webhookEventId": "e1",
                    "deliveryContext": {"isRedelivery": False},
                    "replyToken": "r1",
                    "source": {"type": "user", "userId": user_id},
                    "message": {"id": "m1", "type": "text", "quoteToken": "q1", "text": text},
                }
            ],
        }
    ).encode("utf-8")


def test_line_integration_tenant_isolation(tenant, other_tenant) -> None:
    with tenant_context(tenant):
        LineIntegration.objects.create(channel_access_token="tok")
        assert LineIntegration.objects.count() == 1
        assert line_is_configured() is True
    with tenant_context(other_tenant):
        assert LineIntegration.objects.count() == 0
        assert line_is_configured() is False


def test_push_text_without_integration_raises(tenant) -> None:
    with tenant_context(tenant), pytest.raises(LineNotConfigured):
        push_text("Uabc123", "hi")


def test_tokenless_or_inactive_integration_is_not_configured(tenant) -> None:
    with tenant_context(tenant):
        integ = LineIntegration.objects.create(channel_access_token="", is_active=True)
        assert line_is_configured() is False
        integ.channel_access_token = "tok"
        integ.is_active = False
        integ.save()
        assert line_is_configured() is False


# --- inbound webhook ---------------------------------------------------------
def test_line_webhook_creates_lead_and_activity(client, tenant) -> None:
    from apps.crm.models import Lead

    with tenant_context(tenant):
        LineIntegration.objects.create(
            channel_secret="sekret", channel_access_token="tok", is_active=True
        )
    url = reverse("integrations:line_webhook", args=[tenant.slug])
    body = _text_event_body("Usender1", "สนใจโต๊ะทำงานครับ")
    resp = client.post(
        url,
        data=body,
        content_type="application/json",
        HTTP_X_LINE_SIGNATURE=_line_sig("sekret", body),
    )
    assert resp.status_code == 200
    with tenant_context(tenant):
        lead = Lead.objects.get(line_id="Usender1")
        assert lead.channel == "line"
        assert lead.activities.filter(kind="line", body="สนใจโต๊ะทำงานครับ").exists()
    # a follow-up message links to the same lead
    body2 = _text_event_body("Usender1", "ขอใบเสนอราคาด้วย")
    client.post(
        url,
        data=body2,
        content_type="application/json",
        HTTP_X_LINE_SIGNATURE=_line_sig("sekret", body2),
    )
    with tenant_context(tenant):
        assert Lead.objects.filter(line_id="Usender1").count() == 1
        assert Lead.objects.get(line_id="Usender1").activities.filter(kind="line").count() == 2


def test_line_webhook_bad_signature(client, tenant) -> None:
    from apps.crm.models import Lead

    with tenant_context(tenant):
        LineIntegration.objects.create(channel_secret="sekret", channel_access_token="tok")
    body = _text_event_body("Ux", "hi")
    resp = client.post(
        reverse("integrations:line_webhook", args=[tenant.slug]),
        data=body,
        content_type="application/json",
        HTTP_X_LINE_SIGNATURE="not-the-real-signature",
    )
    assert resp.status_code == 403
    with tenant_context(tenant):
        assert not Lead.objects.filter(line_id="Ux").exists()


def test_line_webhook_without_integration_is_400(client, tenant) -> None:
    body = _text_event_body("Ux", "hi")
    resp = client.post(
        reverse("integrations:line_webhook", args=[tenant.slug]),
        data=body,
        content_type="application/json",
        HTTP_X_LINE_SIGNATURE=_line_sig("whatever", body),
    )
    assert resp.status_code == 400


def test_line_webhook_unknown_tenant_404(client) -> None:
    resp = client.post(
        reverse("integrations:line_webhook", args=["no-such-shop"]),
        data=b"{}",
        content_type="application/json",
    )
    assert resp.status_code == 404
