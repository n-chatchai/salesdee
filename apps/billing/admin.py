from django.contrib import admin

from apps.core.admin import TenantScopedAdmin

from .models import Payment, PaymentAllocation


class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 0
    fields = ("invoice", "amount")


@admin.register(Payment)
class PaymentAdmin(TenantScopedAdmin):
    list_display = ("__str__", "customer", "date", "method", "gross_amount", "status")
    list_filter = ("method", "status")
    search_fields = ("reference", "withholding_cert_ref")
    inlines = [PaymentAllocationInline]


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(TenantScopedAdmin):
    list_display = ("__str__", "payment", "invoice", "amount")
