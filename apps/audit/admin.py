from __future__ import annotations

from django.contrib import admin

from apps.core.admin import TenantScopedAdmin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(TenantScopedAdmin):
    list_display = ("created_at", "action", "actor", "object_type", "object_repr")
    list_filter = ("action", "object_type")
    search_fields = ("action", "object_repr", "object_type")
    readonly_fields = (
        "actor",
        "action",
        "object_type",
        "object_id",
        "object_repr",
        "changes",
        "ip",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
