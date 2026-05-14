from django.contrib import admin

from apps.core.admin import TenantScopedAdmin

from .models import (
    BankAccount,
    CompanyProfile,
    Tenant,
    TenantDomain,
    TenantFeatureOverride,
)


class TenantDomainInline(admin.TabularInline):
    model = TenantDomain
    extra = 0
    fields = ("domain", "is_primary", "verified")


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "plan", "is_active", "trial_ends_at", "created_at")
    list_filter = ("plan", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [TenantDomainInline]


@admin.register(TenantDomain)
class TenantDomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_primary", "verified", "created_at")
    list_filter = ("verified", "is_primary")
    search_fields = ("domain", "tenant__name")
    autocomplete_fields = ("tenant",)


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


@admin.register(TenantFeatureOverride)
class TenantFeatureOverrideAdmin(admin.ModelAdmin):
    """Platform-admin only: override plan-gated module access for a specific tenant.
    Module codes: billing · e_tax · white_label · custom_domain · api · priority_support · sla.
    """

    list_display = ("tenant", "module_code", "mode", "expires_at", "is_active", "updated_at")
    list_filter = ("module_code", "mode")
    search_fields = ("tenant__name", "tenant__slug", "module_code", "reason")
    autocomplete_fields = ("tenant",)
    readonly_fields = ("created_at", "updated_at")
