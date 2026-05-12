from django.contrib import admin

from apps.core.admin import TenantScopedAdmin

from .models import LineIntegration


@admin.register(LineIntegration)
class LineIntegrationAdmin(TenantScopedAdmin):
    list_display = ("__str__", "channel_id", "is_active", "created_at")
    list_filter = ("is_active",)
