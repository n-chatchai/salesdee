"""Outbound LINE messaging via the current tenant's Official Account (Messaging API).

Inbound webhooks (creating/linking leads from incoming messages — FR-2.2) are a later task.
"""

from __future__ import annotations


class LineNotConfigured(Exception):
    """The current tenant has no active LINE integration with a channel access token."""


def _active_integration():
    from .models import LineIntegration

    return LineIntegration.objects.filter(is_active=True).exclude(channel_access_token="").first()


def line_is_configured() -> bool:
    """True if the current tenant has an active LINE OA with a channel access token set."""
    return _active_integration() is not None


def push_text(to: str, text: str) -> None:
    """Push a plain-text message to a LINE user/group id ``to`` using the current tenant's OA.

    Raises ``LineNotConfigured`` if there's no usable integration; otherwise the linebot SDK's
    exception on API/network errors. Must be called inside a tenant context.
    """
    integration = _active_integration()
    if integration is None:
        raise LineNotConfigured("ยังไม่ได้ตั้งค่าการเชื่อม LINE OA สำหรับ workspace นี้")
    from linebot.v3.messaging import (
        ApiClient,
        Configuration,
        MessagingApi,
        PushMessageRequest,
        TextMessage,
    )

    with ApiClient(Configuration(access_token=integration.channel_access_token)) as api_client:
        MessagingApi(api_client).push_message(
            PushMessageRequest(to=to, messages=[TextMessage(text=text)])
        )


def push_quotation_flex(
    to: str,
    *,
    doc_number: str,
    customer_name: str,
    total_text: str,
    valid_text: str,
    view_url: str,
    pdf_url: str,
    company_name: str = "",
) -> None:
    """Push a LINE Flex 'bubble' summarising a quotation, with buttons to open the web view / PDF.
    Raises ``LineNotConfigured`` or SDK errors."""
    integration = _active_integration()
    if integration is None:
        raise LineNotConfigured("ยังไม่ได้ตั้งค่าการเชื่อม LINE OA สำหรับ workspace นี้")
    from linebot.v3.messaging import (
        ApiClient,
        Configuration,
        FlexMessage,
        MessagingApi,
        PushMessageRequest,
    )
    from linebot.v3.messaging.models import FlexContainer

    def _row(label: str, value: str) -> dict:
        return {
            "type": "box",
            "layout": "baseline",
            "spacing": "sm",
            "contents": [
                {"type": "text", "text": label, "color": "#8c8c8c", "size": "sm", "flex": 2},
                {
                    "type": "text",
                    "text": value or "—",
                    "wrap": True,
                    "color": "#2c3e50",
                    "size": "sm",
                    "flex": 5,
                },
            ],
        }

    body_rows = [
        _row("ลูกค้า", customer_name),
        _row("ยอดรวม", total_text),
        _row("ยืนราคาถึง", valid_text),
    ]
    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1B2A3A",
            "paddingAll": "16px",
            "contents": [
                {
                    "type": "text",
                    "text": company_name or "ใบเสนอราคา",
                    "color": "#F6F1E7",
                    "size": "sm",
                },
                {
                    "type": "text",
                    "text": doc_number or "ใบเสนอราคา",
                    "color": "#FFFFFF",
                    "size": "lg",
                    "weight": "bold",
                },
            ],
        },
        "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": body_rows},
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#C8501F",
                    "action": {"type": "uri", "label": "ดูใบเสนอราคา", "uri": view_url},
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "action": {"type": "uri", "label": "ดาวน์โหลด PDF", "uri": pdf_url},
                },
            ],
        },
    }
    with ApiClient(Configuration(access_token=integration.channel_access_token)) as api_client:
        MessagingApi(api_client).push_message(
            PushMessageRequest(
                to=to,
                messages=[
                    FlexMessage(
                        alt_text=f"ใบเสนอราคา {doc_number}".strip(),
                        contents=FlexContainer.from_dict(bubble),
                    )
                ],
            )
        )


def fetch_line_profile_name(line_user_id: str) -> str:
    """Return the LINE display name for ``line_user_id`` via the Messaging API, or "" if LINE isn't
    configured / the API errors / the id is unknown. Must run inside a tenant context. Best-effort
    only — never raises (used by a background task that must not crash the webhook)."""
    integration = _active_integration()
    if integration is None:
        return ""
    try:
        from linebot.v3.messaging import ApiClient, Configuration, MessagingApi

        with ApiClient(Configuration(access_token=integration.channel_access_token)) as api_client:
            profile = MessagingApi(api_client).get_profile(line_user_id)
    except Exception:  # noqa: BLE001 — network/SDK/permission error; give up quietly
        return ""
    return (getattr(profile, "display_name", "") or "").strip()


# --- Inbox: conversations & messages -----------------------------------------
def get_or_create_conversation(line_user_id: str):
    """Find-or-create the LINE conversation for this user in the current tenant, linking it to a
    matching ``Lead`` (creating one if none exists). Must run inside a tenant context."""
    from apps.crm.models import Lead, LeadChannel

    from .models import Conversation, ConversationChannel

    conv, created = Conversation.objects.get_or_create(
        channel=ConversationChannel.LINE,
        external_id=line_user_id,
        defaults={"display_name": f"ลูกค้า LINE {line_user_id[-6:]}"},
    )
    if conv.lead_id is None:
        lead = Lead.objects.filter(line_id=line_user_id).order_by("created_at").first()
        if lead is None:
            lead = Lead.objects.create(
                name=f"ลูกค้า LINE {line_user_id[-6:]}",
                line_id=line_user_id,
                channel=LeadChannel.LINE,
                source="LINE OA",
            )
        conv.lead = lead
        conv.save(update_fields=["lead"])
    if created:
        # Best-effort: fetch the customer's LINE display name in the background (no-ops if LINE
        # isn't configured / the API errors — never blocks or breaks the webhook).
        from .tasks import enrich_conversation_display_name

        enrich_conversation_display_name.enqueue(conv.pk, conv.tenant_id)
    return conv


def _append_message(
    conv, *, direction, text, kind=None, external_id="", media_url="", sender_user=None
):
    from django.utils import timezone

    from .models import Message, MessageDirection, MessageKind

    msg = Message.objects.create(
        conversation=conv,
        direction=direction,
        kind=kind or MessageKind.TEXT,
        text=text,
        external_id=external_id,
        media_url=media_url,
        sender_user=sender_user,
        sent_at=timezone.now(),
    )
    conv.last_message_at = msg.sent_at
    conv.last_message_preview = (text or msg.get_kind_display())[:255]
    update_fields = ["last_message_at", "last_message_preview"]
    if direction == MessageDirection.IN:
        conv.unread_count = (conv.unread_count or 0) + 1
        update_fields.append("unread_count")
    conv.save(update_fields=update_fields)
    return msg


def record_outbound_text(conv, text: str, *, sender_user=None, external_id=""):
    """Log an outbound text we sent on this conversation (call after ``push_text`` succeeds)."""
    from .models import MessageDirection

    return _append_message(
        conv,
        direction=MessageDirection.OUT,
        text=text,
        external_id=external_id,
        sender_user=sender_user,
    )


def _record_inbound(line_user_id: str, *, text: str, kind=None, external_id: str = "") -> None:
    """Record an inbound LINE message: append it to the user's conversation (creating the
    conversation + linked lead if needed); for text, also mirror it onto the lead's activity
    timeline. ``kind`` defaults to ``MessageKind.TEXT``."""
    from apps.crm.models import Activity, ActivityKind
    from apps.tenants.quota import increment_usage

    from .models import MessageDirection, MessageKind

    conv = get_or_create_conversation(line_user_id)
    _append_message(
        conv, direction=MessageDirection.IN, text=text, kind=kind, external_id=external_id
    )
    increment_usage(conv.tenant, "line_msgs")
    if conv.lead_id and kind in (None, MessageKind.TEXT) and text:
        if not conv.lead.message:
            conv.lead.message = text
            conv.lead.save(update_fields=["message"])
        Activity.objects.create(lead=conv.lead, kind=ActivityKind.LINE, body=text)


def _record_inbound_text(line_user_id: str, text: str) -> None:
    _record_inbound(line_user_id, text=text)


def _inbound_placeholder(message) -> tuple[object, str]:
    """Map a non-text LINE message-content object to (MessageKind, placeholder text)."""
    from linebot.v3.webhooks import (
        AudioMessageContent,
        FileMessageContent,
        ImageMessageContent,
        LocationMessageContent,
        StickerMessageContent,
        VideoMessageContent,
    )

    from .models import MessageKind

    if isinstance(message, ImageMessageContent):
        return MessageKind.IMAGE, "[รูปภาพ]"
    if isinstance(message, StickerMessageContent):
        return MessageKind.STICKER, "[สติกเกอร์]"
    if isinstance(message, FileMessageContent):
        name = getattr(message, "file_name", "") or "ไฟล์"
        return MessageKind.FILE, f"[ไฟล์] {name}"
    if isinstance(message, VideoMessageContent):
        return MessageKind.VIDEO, "[วิดีโอ]"
    if isinstance(message, AudioMessageContent):
        return MessageKind.AUDIO, "[เสียง]"
    if isinstance(message, LocationMessageContent):
        label = getattr(message, "title", "") or getattr(message, "address", "") or ""
        return MessageKind.LOCATION, f"[ตำแหน่ง] {label}".strip()
    return MessageKind.OTHER, "[ข้อความ]"


def process_line_events(events: list) -> int:
    """Turn parsed LINE webhook events into conversation messages (and, for text, lead activities).
    Handles user messages of any kind (text + image/sticker/file/video/audio/location); media bytes
    aren't downloaded — only the message is recorded. Group/room messages are ignored. Returns how
    many were recorded.

    The current tenant context must be active (the webhook view sets it from the URL slug).
    """
    from linebot.v3.webhooks import MessageEvent, TextMessageContent, UserSource

    count = 0
    for event in events:
        if not (
            isinstance(event, MessageEvent)
            and isinstance(event.source, UserSource)
            and getattr(event.source, "user_id", None)
        ):
            continue
        ext_id = str(getattr(event.message, "id", "") or "")
        if isinstance(event.message, TextMessageContent):
            _record_inbound(event.source.user_id, text=event.message.text, external_id=ext_id)
        else:
            kind, placeholder = _inbound_placeholder(event.message)
            _record_inbound(event.source.user_id, text=placeholder, kind=kind, external_id=ext_id)
        count += 1
    return count
