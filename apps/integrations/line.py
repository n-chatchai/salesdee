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
