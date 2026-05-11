from __future__ import annotations

from django import forms

from apps.catalog.models import Product, ProductVariant
from apps.core.forms import set_queryset, tenant_users
from apps.crm.models import Contact, Customer
from apps.tenants.models import BankAccount

from .models import SalesDocLine, SalesDocument


class QuotationForm(forms.ModelForm):
    class Meta:
        model = SalesDocument
        fields = [
            "customer",
            "contact",
            "reference",
            "salesperson",
            "issue_date",
            "valid_until",
            "end_discount_kind",
            "end_discount_value",
            "payment_terms",
            "lead_time",
            "warranty",
            "notes",
            "bank_account",
        ]
        # price_mode is omitted for now — the totals engine only does EXCLUSIVE pricing (TODO).
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "valid_until": forms.DateInput(attrs={"type": "date"}),
            "payment_terms": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_queryset(self, "customer", Customer.objects.filter(is_archived=False))
        set_queryset(self, "contact", Contact.objects.all())
        set_queryset(self, "salesperson", tenant_users())
        set_queryset(self, "bank_account", BankAccount.objects.all())
        for name in ("customer", "contact", "salesperson", "bank_account", "end_discount_value"):
            self.fields[name].required = False
        self.fields["end_discount_value"].initial = 0

    def clean_end_discount_value(self):
        return self.cleaned_data.get("end_discount_value") or 0


class SalesDocLineForm(forms.ModelForm):
    class Meta:
        model = SalesDocLine
        fields = [
            "group_label",
            "line_type",
            "product",
            "variant",
            "description",
            "dimensions",
            "material",
            "quantity",
            "unit",
            "unit_price",
            "discount_kind",
            "discount_value",
            "tax_type",
            "withholding_rate",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_queryset(self, "product", Product.objects.filter(is_active=True))
        set_queryset(self, "variant", ProductVariant.objects.filter(is_active=True))
        for name in (
            "product", "variant", "description", "line_type", "unit", "quantity",
            "unit_price", "discount_kind", "discount_value", "tax_type", "withholding_rate",
        ):  # fmt: skip
            self.fields[name].required = False
        self.fields["quantity"].initial = 1
        self.fields["unit_price"].initial = 0
        self.fields["unit"].initial = "ชิ้น"

    def _num(self, name, default):
        value = self.cleaned_data.get(name)
        return value if value is not None else default

    def clean_quantity(self):
        return self._num("quantity", 1)

    def clean_unit_price(self):
        return self._num("unit_price", 0)

    def clean_discount_value(self):
        return self._num("discount_value", 0)

    def clean_withholding_rate(self):
        return self._num("withholding_rate", 0)

    def clean_unit(self):
        return self.cleaned_data.get("unit") or "ชิ้น"

    def clean_line_type(self):
        return (
            self.cleaned_data.get("line_type") or SalesDocLine._meta.get_field("line_type").default
        )

    def clean_discount_kind(self):
        return (
            self.cleaned_data.get("discount_kind")
            or SalesDocLine._meta.get_field("discount_kind").default
        )

    def clean_tax_type(self):
        return self.cleaned_data.get("tax_type") or SalesDocLine._meta.get_field("tax_type").default

    def clean(self):
        cleaned = super().clean()
        desc = (cleaned.get("description") or "").strip()
        if not desc and not cleaned.get("product") and not cleaned.get("variant"):
            self.add_error("description", "ระบุรายละเอียด หรือเลือกสินค้าจากแคตตาล็อก")
        return cleaned
