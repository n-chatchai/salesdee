from django.contrib import admin

from apps.core.admin import TenantScopedAdmin

from .models import (
    BundleItem,
    Product,
    ProductCategory,
    ProductImage,
    ProductOption,
    ProductVariant,
)


@admin.register(ProductCategory)
class ProductCategoryAdmin(TenantScopedAdmin):
    list_display = ("name", "parent", "order")
    search_fields = ("name",)
    ordering = ("order", "name")


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ("image", "caption", "sort_order")


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ("name", "sku", "price", "cost", "is_active")


class ProductOptionInline(admin.TabularInline):
    model = ProductOption
    extra = 0
    fields = ("name", "extra_price", "is_active")


class BundleItemInline(admin.TabularInline):
    model = BundleItem
    fk_name = "bundle"
    extra = 0
    fields = ("component", "variant", "quantity")
    autocomplete_fields = ("component", "variant")


@admin.register(Product)
class ProductAdmin(TenantScopedAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "default_price",
        "tax_type",
        "is_bundle",
        "is_active",
    )
    list_filter = ("tax_type", "is_bundle", "is_active", "category")
    search_fields = ("code", "name", "name_en", "material", "tags")
    autocomplete_fields = ("category",)
    inlines = [ProductImageInline, ProductVariantInline, ProductOptionInline, BundleItemInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(TenantScopedAdmin):
    list_display = ("product", "name", "sku", "price", "is_active")
    search_fields = ("name", "sku", "product__name", "product__code")
    autocomplete_fields = ("product",)
