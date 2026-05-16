from __future__ import annotations

import json

from django import forms

from apps.core.forms import set_queryset

from .models import Product, ProductCategory


class QuoteRequestForm(forms.Form):
    """Public, anonymous Path A quote-request form (tenant-site frame e).
    Validates contact info + cart payload; the view then creates a SalesDocument
    with source=WEBSITE, status=REQUEST."""

    name = forms.CharField(label="ชื่อ-นามสกุล", max_length=200)
    phone = forms.CharField(label="เบอร์โทร", max_length=40)
    contact = forms.CharField(label="LINE ID หรืออีเมล", max_length=200)
    company_name = forms.CharField(label="บริษัท", max_length=255, required=False)
    address = forms.CharField(
        label="ที่อยู่ส่งของ", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    install_date = forms.CharField(label="กำหนดติดตั้ง", max_length=100, required=False)
    service = forms.CharField(label="บริการ", max_length=100, required=False)
    notes = forms.CharField(
        label="หมายเหตุ", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    tos = forms.BooleanField(label="ยอมรับเงื่อนไข", required=True)
    cart = forms.CharField(widget=forms.HiddenInput, required=False)

    def clean_cart(self):
        raw = (self.cleaned_data.get("cart") or "").strip()
        if not raw:
            return []
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("ข้อมูลตะกร้าผิดพลาด") from exc
        if not isinstance(items, list):
            raise forms.ValidationError("ข้อมูลตะกร้าผิดพลาด")
        cleaned = []
        for it in items[:50]:
            try:
                pid = int(it.get("id"))
                qty = max(1, int(it.get("qty", 1)))
            except (TypeError, ValueError):
                continue
            cleaned.append({"id": pid, "qty": qty})
        return cleaned


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
            "lead_time_days",
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
