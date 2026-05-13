from django.contrib import admin

from apps.core.admin import TenantScopedAdmin

from .models import Conversation, LineIntegration, Message


@admin.register(LineIntegration)
class LineIntegrationAdmin(TenantScopedAdmin):
    list_display = ("__str__", "channel_id", "is_active", "created_at")
    list_filter = ("is_active",)


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ("direction", "kind", "text", "sender_user", "sent_at")
    readonly_fields = ("sent_at",)


@admin.register(Conversation)
class ConversationAdmin(TenantScopedAdmin):
    list_display = (
        "__str__",
        "channel",
        "status",
        "assigned_to",
        "last_message_at",
        "unread_count",
    )
    list_filter = ("channel", "status")
    search_fields = ("external_id", "display_name")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(TenantScopedAdmin):
    list_display = ("__str__", "conversation", "direction", "kind", "sent_at")
    list_filter = ("direction", "kind")
