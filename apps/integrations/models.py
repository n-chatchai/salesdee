"""External integrations.  Spec: REQUIREMENTS.md §4.16.

Phase 1: LINE Official Account (receive/send messages, send documents, customer notifications) +
email (in/out). Stores per-tenant LINE channel credentials and (later) a unified Message log.
Phase 3: public REST API / webhooks; export/sync to accounting software (FlowAccount/PEAK/Express).

Tenant-owned config (e.g. LineIntegration) → ``TenantScopedModel`` (+ add ``enable_tenant_rls``).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TenantScopedModel


class LineIntegration(TenantScopedModel):
    """A tenant's LINE Official Account Messaging-API credentials. One per tenant.

    ``channel_access_token`` is a long-lived channel access token (used to push messages);
    ``channel_secret`` verifies inbound webhook signatures (inbound handling is a later task).
    TODO: encrypt these at rest (NFR §7) — for now they live in a plaintext config row that only
    platform/owner admins touch.
    """

    channel_id = models.CharField("Channel ID", max_length=50, blank=True)
    channel_secret = models.CharField("Channel secret", max_length=100, blank=True)
    channel_access_token = models.TextField("Channel access token", blank=True)
    is_active = models.BooleanField("เปิดใช้งาน", default=True)

    class Meta:
        verbose_name = "การเชื่อม LINE OA"
        verbose_name_plural = "การเชื่อม LINE OA"
        constraints = [
            models.UniqueConstraint(fields=["tenant"], name="uniq_line_integration_per_tenant")
        ]

    def __str__(self) -> str:
        return f"LINE OA {self.channel_id or self.tenant_id}"


# --- Unified inbox: conversations & messages ---------------------------------
# A "conversation" is one chat thread with a contact on an external channel (LINE first); a
# "message" is one inbound/outbound message in it. The inbox screen (FR-2.x) reads these; the
# CRM ``Lead``/``Activity`` records still exist alongside (a conversation may link to a lead and,
# once identified, a customer). PRD §9: keep raw message content scoped; don't ship it off-tenant.
class ConversationChannel(models.TextChoices):
    LINE = "line", "LINE"


class ConversationStatus(models.TextChoices):
    OPEN = "open", "เปิด"
    SNOOZED = "snoozed", "พักไว้"
    CLOSED = "closed", "ปิด"


class Conversation(TenantScopedModel):
    channel = models.CharField(
        "ช่องทาง",
        max_length=20,
        choices=ConversationChannel.choices,
        default=ConversationChannel.LINE,
    )
    external_id = models.CharField("รหัสผู้ใช้ภายนอก", max_length=100, help_text="เช่น LINE user id")
    display_name = models.CharField("ชื่อที่แสดง", max_length=255, blank=True)
    customer = models.ForeignKey(
        "crm.Customer",
        on_delete=models.SET_NULL,
        related_name="conversations",
        null=True,
        blank=True,
    )
    lead = models.ForeignKey(
        "crm.Lead",
        on_delete=models.SET_NULL,
        related_name="conversations",
        null=True,
        blank=True,
    )
    status = models.CharField(
        "สถานะ", max_length=20, choices=ConversationStatus.choices, default=ConversationStatus.OPEN
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_conversations",
        null=True,
        blank=True,
    )
    last_message_at = models.DateTimeField("ข้อความล่าสุด", null=True, blank=True)
    last_message_preview = models.CharField("ตัวอย่างข้อความล่าสุด", max_length=255, blank=True)
    unread_count = models.PositiveIntegerField("ยังไม่อ่าน", default=0)

    class Meta:
        ordering = ("-last_message_at", "-created_at")
        verbose_name = "บทสนทนา"
        verbose_name_plural = "บทสนทนา"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "channel", "external_id"],
                name="uniq_conversation_per_external_id",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "-last_message_at"]),
            models.Index(fields=["tenant", "assigned_to"]),
        ]

    def __str__(self) -> str:
        return self.display_name or f"{self.get_channel_display()} {self.external_id[-6:]}"


class MessageDirection(models.TextChoices):
    IN = "in", "ขาเข้า"
    OUT = "out", "ขาออก"


class MessageKind(models.TextChoices):
    TEXT = "text", "ข้อความ"
    IMAGE = "image", "รูปภาพ"
    STICKER = "sticker", "สติกเกอร์"
    FILE = "file", "ไฟล์"
    VIDEO = "video", "วิดีโอ"
    AUDIO = "audio", "เสียง"
    LOCATION = "location", "ตำแหน่ง"
    OTHER = "other", "อื่น ๆ"


class Message(TenantScopedModel):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    direction = models.CharField("ทิศทาง", max_length=4, choices=MessageDirection.choices)
    kind = models.CharField(
        "ชนิด", max_length=20, choices=MessageKind.choices, default=MessageKind.TEXT
    )
    text = models.TextField("ข้อความ", blank=True)
    media_url = models.URLField("สื่อ", blank=True)
    external_id = models.CharField("รหัสข้อความภายนอก", max_length=100, blank=True)
    ai_parsed = models.JSONField("ผลวิเคราะห์ AI", default=dict, blank=True)
    sender_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="sent_messages",
        null=True,
        blank=True,
        help_text="ผู้ส่ง (เฉพาะข้อความขาออกที่ส่งโดยพนักงาน)",
    )
    sent_at = models.DateTimeField("เวลาส่ง")

    class Meta:
        ordering = ("sent_at", "id")
        verbose_name = "ข้อความ"
        verbose_name_plural = "ข้อความ"
        indexes = [models.Index(fields=["conversation", "sent_at"])]

    def __str__(self) -> str:
        return f"{self.get_direction_display()} · {self.text[:40] or self.get_kind_display()}"
