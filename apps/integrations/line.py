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


# --- Inbound webhook ---------------------------------------------------------
def _record_inbound_text(line_user_id: str, text: str) -> None:
    """Find-or-create the LINE lead for this user (current tenant) and log the message as an Activity.
    TODO: enrich the lead's name from the LINE profile API (in a background task)."""
    from apps.crm.models import Activity, ActivityKind, Lead, LeadChannel

    lead = Lead.objects.filter(line_id=line_user_id).order_by("created_at").first()
    if lead is None:
        lead = Lead.objects.create(
            name=f"ลูกค้า LINE {line_user_id[-6:]}",
            line_id=line_user_id,
            channel=LeadChannel.LINE,
            source="LINE OA",
            message=text,
        )
    Activity.objects.create(lead=lead, kind=ActivityKind.LINE, body=text)


def process_line_events(events: list) -> int:
    """Turn parsed LINE webhook events into lead activities. Text messages from a user only (group/
    room messages and non-text messages are ignored). Returns how many were recorded.

    The current tenant context must be active (the webhook view sets it from the URL slug).
    """
    from linebot.v3.webhooks import MessageEvent, TextMessageContent, UserSource

    count = 0
    for event in events:
        if (
            isinstance(event, MessageEvent)
            and isinstance(event.source, UserSource)
            and isinstance(event.message, TextMessageContent)
            and event.source.user_id
        ):
            _record_inbound_text(event.source.user_id, event.message.text)
            count += 1
    return count
