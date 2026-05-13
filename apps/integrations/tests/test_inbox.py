from __future__ import annotations

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context
from apps.integrations.line import _record_inbound_text, record_outbound_text
from apps.integrations.models import Conversation, ConversationStatus, Message, MessageDirection

pytestmark = pytest.mark.django_db


def test_inbound_text_creates_conversation_and_message(tenant) -> None:
    with tenant_context(tenant):
        _record_inbound_text("Ucustomer1", "สนใจโต๊ะทำงานครับ")
        conv = Conversation.objects.get(external_id="Ucustomer1")
        assert conv.channel == "line"
        assert conv.lead is not None
        assert conv.unread_count == 1
        assert conv.last_message_preview == "สนใจโต๊ะทำงานครับ"
        msg = conv.messages.get()
        assert msg.direction == MessageDirection.IN
        assert msg.text == "สนใจโต๊ะทำงานครับ"
        # follow-up reuses the same conversation
        _record_inbound_text("Ucustomer1", "ขอใบเสนอราคาด้วย")
        conv.refresh_from_db()
        assert Conversation.objects.filter(external_id="Ucustomer1").count() == 1
        assert conv.messages.count() == 2
        assert conv.unread_count == 2


def test_record_outbound_resets_nothing_but_appends(tenant, user) -> None:
    with tenant_context(tenant):
        _record_inbound_text("Uc2", "สวัสดีครับ")
        conv = Conversation.objects.get(external_id="Uc2")
        record_outbound_text(conv, "ได้เลยครับ เดี๋ยวจัดให้", sender_user=user)
        conv.refresh_from_db()
        assert conv.messages.count() == 2
        out = conv.messages.filter(direction=MessageDirection.OUT).get()
        assert out.sender_user_id == user.id
        assert conv.last_message_preview == "ได้เลยครับ เดี๋ยวจัดให้"
        assert conv.unread_count == 1  # outbound doesn't bump unread


def test_conversation_and_message_tenant_isolation(tenant, other_tenant) -> None:
    with tenant_context(tenant):
        _record_inbound_text("Uleak", "ข้อความลับ")
        assert Conversation.objects.count() == 1
        assert Message.objects.count() == 1
    with tenant_context(other_tenant):
        assert Conversation.objects.count() == 0
        assert Message.objects.count() == 0
        assert not Conversation.objects.filter(external_id="Uleak").exists()


def test_inbox_requires_login(client) -> None:
    assert client.get(reverse("integrations:inbox")).status_code == 302


def test_inbox_lists_and_opens_conversation_marks_read(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        _record_inbound_text("Uview", "อยากได้เก้าอี้สำนักงาน")
        conv = Conversation.objects.get(external_id="Uview")
    client.force_login(user)
    resp = client.get(reverse("integrations:inbox"))
    assert resp.status_code == 200
    assert "อยากได้เก้าอี้สำนักงาน" in resp.content.decode()
    resp = client.get(reverse("integrations:conversation", args=[conv.pk]))
    assert resp.status_code == 200
    with tenant_context(tenant):
        conv.refresh_from_db()
        assert conv.unread_count == 0


def test_reply_pushes_and_records(client, user, membership, tenant, monkeypatch) -> None:
    from apps.integrations import line as line_mod

    with tenant_context(tenant):
        _record_inbound_text("Ureply", "ขอราคาโต๊ะ")
        conv = Conversation.objects.get(external_id="Ureply")
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(line_mod, "push_text", lambda to, text: sent.append((to, text)))
    # the view imports push_text from .line into its module namespace
    from apps.integrations import views as views_mod

    monkeypatch.setattr(views_mod, "push_text", lambda to, text: sent.append((to, text)))
    client.force_login(user)
    resp = client.post(
        reverse("integrations:conversation_reply", args=[conv.pk]), {"text": "ได้ครับ 3,500 บาท"}
    )
    assert resp.status_code == 200
    assert sent == [("Ureply", "ได้ครับ 3,500 บาท")]
    with tenant_context(tenant):
        conv.refresh_from_db()
        assert conv.messages.filter(direction=MessageDirection.OUT, text="ได้ครับ 3,500 บาท").exists()


def test_assign_to_me(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        _record_inbound_text("Uassign", "hi")
        conv = Conversation.objects.get(external_id="Uassign")
    client.force_login(user)
    client.post(reverse("integrations:conversation_assign", args=[conv.pk]))
    with tenant_context(tenant):
        conv.refresh_from_db()
        assert conv.assigned_to_id == user.id
    client.post(reverse("integrations:conversation_assign", args=[conv.pk]), {"unassign": "1"})
    with tenant_context(tenant):
        conv.refresh_from_db()
        assert conv.assigned_to_id is None


def test_close_and_reopen(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        _record_inbound_text("Uclose", "hi")
        conv = Conversation.objects.get(external_id="Uclose")
    client.force_login(user)
    client.post(reverse("integrations:conversation_status", args=[conv.pk]), {"status": "closed"})
    with tenant_context(tenant):
        conv.refresh_from_db()
        assert conv.status == ConversationStatus.CLOSED


# --- non-text inbound (item 2) ----------------------------------------------
def _image_event_payload(user_id: str):
    from linebot.v3.webhooks import ImageMessageContent, MessageEvent, UserSource

    return MessageEvent(
        message=ImageMessageContent(id="img-1", contentProvider={"type": "line"}, quoteToken="qt"),
        timestamp=1,
        source=UserSource(userId=user_id),
        replyToken="r",
        mode="active",
        webhookEventId="e",
        deliveryContext={"isRedelivery": False},
    )


def test_image_event_records_image_message(tenant) -> None:
    from apps.integrations.line import process_line_events

    with tenant_context(tenant):
        n = process_line_events([_image_event_payload("Upic")])
        assert n == 1
        conv = Conversation.objects.get(external_id="Upic")
        msg = conv.messages.get()
        assert msg.kind == "image"
        assert msg.text == "[รูปภาพ]"
        assert msg.external_id == "img-1"
        assert conv.last_message_preview == "[รูปภาพ]"
        # non-text doesn't get mirrored onto the lead's activity timeline
        assert conv.lead is not None
        assert conv.lead.activities.count() == 0


# --- LINE profile-name enrichment (item 3) ----------------------------------
def test_enrich_sets_display_name_and_lead_name(tenant, monkeypatch) -> None:
    from apps.integrations.models import LineIntegration

    monkeypatch.setattr("apps.integrations.line.fetch_line_profile_name", lambda _uid: "คุณสมชาย")
    with tenant_context(tenant):
        LineIntegration.objects.create(channel_access_token="tok", is_active=True)
        # creating the conversation enqueues the enrichment task (runs synchronously here)
        _record_inbound_text("Uenrich", "สวัสดีครับ")
        conv = Conversation.objects.get(external_id="Uenrich")
        assert conv.display_name == "คุณสมชาย"
        assert conv.lead is not None
        assert conv.lead.name == "คุณสมชาย"


# --- AI customer summary (item 6) -------------------------------------------
def test_ai_summary_when_ai_off(client, user, membership, tenant, settings) -> None:
    settings.ANTHROPIC_API_KEY = ""
    with tenant_context(tenant):
        _record_inbound_text("Usum", "อยากได้โต๊ะทำงาน")
        conv = Conversation.objects.get(external_id="Usum")
    client.force_login(user)
    resp = client.post(reverse("integrations:conversation_ai_summary", args=[conv.pk]))
    assert resp.status_code == 200
    assert "ยังไม่ได้ตั้งค่าผู้ช่วย AI" in resp.content.decode()
