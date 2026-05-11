from django.contrib import admin

from apps.core.admin import TenantScopedAdmin

from .models import BankAccount, CompanyProfile, Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "plan", "is_active", "trial_ends_at", "created_at")
    list_filter = ("plan", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("name_th", "tenant", "tax_id", "branch_kind", "phone")
    search_fields = ("name_th", "name_en", "tax_id", "tenant__name")
    autocomplete_fields = ("tenant",)


@admin.register(BankAccount)
class BankAccountAdmin(TenantScopedAdmin):
    list_display = ("bank_name", "account_number", "account_name", "is_default")
    list_filter = ("bank_name", "is_default")
    search_fields = ("bank_name", "account_number", "account_name")
