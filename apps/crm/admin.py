from django.contrib import admin

from apps.core.admin import TenantScopedAdmin

from .models import Activity, Contact, Customer, Deal, Lead, PipelineStage, SalesTarget, Task


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0
    fields = ("name", "title", "department", "phone", "email", "line_id", "is_primary")


@admin.register(Customer)
class CustomerAdmin(TenantScopedAdmin):
    list_display = ("name", "kind", "tax_id", "default_credit_days", "is_archived")
    list_filter = ("kind", "is_archived")
    search_fields = ("name", "name_en", "tax_id")
    inlines = [ContactInline]


@admin.register(Contact)
class ContactAdmin(TenantScopedAdmin):
    list_display = ("name", "customer", "title", "phone", "email", "is_primary")
    search_fields = ("name", "phone", "email", "customer__name")
    autocomplete_fields = ("customer",)


@admin.register(PipelineStage)
class PipelineStageAdmin(TenantScopedAdmin):
    list_display = ("name", "order", "kind", "default_probability")
    list_filter = ("kind",)
    search_fields = ("name",)
    ordering = ("order",)


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0
    fields = ("kind", "body", "occurred_at", "created_by")
    autocomplete_fields = ("created_by",)


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ("kind", "description", "due_at", "assignee", "status")
    autocomplete_fields = ("assignee",)


@admin.register(Deal)
class DealAdmin(TenantScopedAdmin):
    list_display = (
        "name",
        "customer",
        "stage",
        "status",
        "estimated_value",
        "probability",
        "expected_close_date",
        "owner",
    )
    list_filter = ("status", "stage", "channel")
    search_fields = ("name", "customer__name", "source")
    autocomplete_fields = ("customer", "contact", "owner")
    inlines = [ActivityInline, TaskInline]


@admin.register(Activity)
class ActivityAdmin(TenantScopedAdmin):
    list_display = ("kind", "deal", "customer", "occurred_at", "created_by")
    list_filter = ("kind",)
    search_fields = ("body", "deal__name", "customer__name")
    autocomplete_fields = ("deal", "customer", "contact", "created_by")


@admin.register(Task)
class TaskAdmin(TenantScopedAdmin):
    list_display = ("description", "kind", "deal", "customer", "due_at", "assignee", "status")
    list_filter = ("status", "kind")
    search_fields = ("description", "deal__name", "customer__name")
    autocomplete_fields = ("deal", "customer", "assignee")


@admin.register(Lead)
class LeadAdmin(TenantScopedAdmin):
    list_display = (
        "name",
        "company_name",
        "channel",
        "product_interest",
        "status",
        "assigned_to",
        "created_at",
    )
    list_filter = ("status", "channel")
    search_fields = ("name", "company_name", "phone", "email", "product_interest")
    autocomplete_fields = ("assigned_to", "customer", "deal")


@admin.register(SalesTarget)
class SalesTargetAdmin(TenantScopedAdmin):
    list_display = ("year", "month", "salesperson", "amount")
    list_filter = ("year", "month")
