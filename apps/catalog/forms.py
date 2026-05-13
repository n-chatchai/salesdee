from __future__ import annotations

from django import forms

from apps.core.forms import set_queryset

from .models import Product, ProductCategory


class ProductCategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ["name", "parent", "order"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # parent is a self-FK to a TenantScopedModel -> re-bind per request (CLAUDE.md §5).
        qs = ProductCategory.objects.all()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        set_queryset(self, "parent", qs)
        self.fields["parent"].required = False

    def clean_parent(self):
        parent = self.cleaned_data.get("parent")
        if parent and self.instance.pk and parent.pk == self.instance.pk:
            raise forms.ValidationError("หมวดแม่ต้องไม่ใช่ตัวเอง")
        return parent


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
