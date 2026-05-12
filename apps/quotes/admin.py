from django.contrib import admin

from apps.core.admin import TenantScopedAdmin

from .models import (
    DocumentNumberSequence,
    QuotationRevision,
    QuotationShareLink,
    SalesDocLine,
    SalesDocument,
)


class SalesDocLineInline(admin.TabularInline):
    model = SalesDocLine
    extra = 0
    fields = (
        "position", "group_label", "line_type", "product", "variant", "description",
        "dimensions", "material", "quantity", "unit", "unit_price", "discount_kind",
        "discount_value", "tax_type", "withholding_rate",
    )  # fmt: skip
    autocomplete_fields = ("product", "variant")


@admin.register(SalesDocument)
class SalesDocumentAdmin(TenantScopedAdmin):
    list_display = ("doc_number", "doc_type", "customer", "status", "issue_date", "valid_until")
    list_filter = ("doc_type", "status")
    search_fields = ("doc_number", "reference", "customer__name")
    autocomplete_fields = ("deal", "customer", "contact", "salesperson", "bank_account")
    inlines = [SalesDocLineInline]


@admin.register(DocumentNumberSequence)
class DocumentNumberSequenceAdmin(TenantScopedAdmin):
    list_display = ("doc_type", "year", "last_number")
    list_filter = ("doc_type", "year")


@admin.register(QuotationShareLink)
class QuotationShareLinkAdmin(admin.ModelAdmin):
    list_display = ("token", "document", "tenant", "expires_at", "revoked", "created_at")
    list_filter = ("revoked", "tenant")
    search_fields = ("token", "document__doc_number")


@admin.register(QuotationRevision)
class QuotationRevisionAdmin(TenantScopedAdmin):
    list_display = ("document", "revision", "reason", "changed_by", "created_at")
    search_fields = ("document__doc_number", "reason")
    readonly_fields = ("document", "revision", "snapshot", "reason", "changed_by")
