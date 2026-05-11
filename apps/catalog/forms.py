from __future__ import annotations

from django import forms

from apps.core.forms import set_queryset

from .models import Product, ProductCategory


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "category",
            "code",
            "name",
            "name_en",
            "description",
            "unit",
            "default_price",
            "cost",
            "tax_type",
            "width_mm",
            "depth_mm",
            "height_mm",
            "material",
            "finish",
            "color_code",
            "hardware_brand",
            "standard",
            "is_bundle",
            "is_active",
            "tags",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # category is a TenantScopedModel FK -> re-bind queryset per request (CLAUDE.md §5).
        set_queryset(self, "category", ProductCategory.objects.all())
        for name in ("category", "cost", "width_mm", "depth_mm", "height_mm"):
            self.fields[name].required = False
        self.fields["default_price"].required = False
        self.fields["default_price"].initial = 0

    def clean_default_price(self):
        return self.cleaned_data.get("default_price") or 0
