"""Furniture-aware product catalog. Spec: REQUIREMENTS.md §4.6. All models are tenant-owned."""

from __future__ import annotations

from django.db import models

from apps.core.models import TenantScopedModel


class TaxType(models.TextChoices):
    VAT7 = "vat7", "VAT 7%"
    VAT0 = "vat0", "VAT 0% (เช่น ส่งออก)"
    EXEMPT = "exempt", "ยกเว้น VAT"
    NONE = "none", "ไม่คิด VAT"


class ProductCategory(TenantScopedModel):
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, related_name="children", null=True, blank=True
    )
    name = models.CharField("ชื่อหมวด", max_length=150)
    order = models.PositiveIntegerField("ลำดับ", default=0)

    class Meta:
        ordering = ("order", "name")
        verbose_name = "หมวดสินค้า"
        verbose_name_plural = "หมวดสินค้า"

    def __str__(self) -> str:
        return f"{self.parent} › {self.name}" if self.parent_id else self.name


class Product(TenantScopedModel):
    category = models.ForeignKey(
        ProductCategory, on_delete=models.SET_NULL, related_name="products", null=True, blank=True
    )
    code = models.CharField("รหัส/รุ่น", max_length=64, blank=True, db_index=True)
    name = models.CharField("ชื่อสินค้า", max_length=255)
    name_en = models.CharField("ชื่อ (อังกฤษ)", max_length=255, blank=True)
    description = models.TextField("รายละเอียด", blank=True)
    unit = models.CharField("หน่วยนับ", max_length=30, default="ชิ้น")
    default_price = models.DecimalField("ราคาขายเริ่มต้น", max_digits=18, decimal_places=2, default=0)
    cost = models.DecimalField("ต้นทุน", max_digits=18, decimal_places=2, null=True, blank=True)
    tax_type = models.CharField("ภาษี", max_length=10, choices=TaxType.choices, default=TaxType.VAT7)
    # Furniture-specific attributes
    width_mm = models.PositiveIntegerField("กว้าง (มม.)", null=True, blank=True)
    depth_mm = models.PositiveIntegerField("ลึก (มม.)", null=True, blank=True)
    height_mm = models.PositiveIntegerField("สูง (มม.)", null=True, blank=True)
    material = models.CharField("วัสดุ/ผิว", max_length=150, blank=True)
    finish = models.CharField("สี/ผิวสำเร็จ", max_length=150, blank=True)
    color_code = models.CharField("รหัสสี", max_length=50, blank=True)
    hardware_brand = models.CharField(
        "ยี่ห้ออุปกรณ์", max_length=100, blank=True, help_text="เช่น บานพับ/รางลิ้นชัก"
    )
    standard = models.CharField("มาตรฐาน", max_length=100, blank=True, help_text="เช่น มอก. ...")
    is_bundle = models.BooleanField("เป็นชุด (มีรายการย่อย)", default=False)
    is_active = models.BooleanField("เปิดขาย", default=True)
    tags = models.CharField("แท็ก", max_length=255, blank=True, help_text="คั่นด้วยจุลภาค")

    class Meta:
        ordering = ("name",)
        verbose_name = "สินค้า"
        verbose_name_plural = "สินค้า"
        indexes = [models.Index(fields=["tenant", "name"]), models.Index(fields=["tenant", "code"])]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "code"],
                condition=models.Q(code__gt=""),
                name="uniq_product_code_per_tenant",
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}".strip()

    @property
    def dimensions(self) -> str:
        parts = [v for v in (self.width_mm, self.depth_mm, self.height_mm) if v]
        return " × ".join(f"{v}" for v in parts) + " มม." if parts else ""


class ProductImage(TenantScopedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("รูป", upload_to="product_images/")
    caption = models.CharField("คำบรรยาย", max_length=255, blank=True)
    sort_order = models.PositiveIntegerField("ลำดับ", default=0)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "รูปสินค้า"
        verbose_name_plural = "รูปสินค้า"

    def __str__(self) -> str:
        return self.caption or f"รูปของ {self.product}"


class ProductVariant(TenantScopedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField("รุ่นย่อย", max_length=255, help_text='เช่น "W150 / สีโอ๊ค"')
    sku = models.CharField("SKU", max_length=64, blank=True)
    price = models.DecimalField("ราคา", max_digits=18, decimal_places=2, default=0)
    cost = models.DecimalField("ต้นทุน", max_digits=18, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField("เปิดขาย", default=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "รุ่นย่อยสินค้า"
        verbose_name_plural = "รุ่นย่อยสินค้า"

    def __str__(self) -> str:
        return f"{self.product} — {self.name}"


class ProductOption(TenantScopedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="options")
    name = models.CharField("ออปชันเสริม", max_length=255, help_text="เช่น เพิ่มไฟ LED ใต้ตู้")
    extra_price = models.DecimalField("ราคาเพิ่ม", max_digits=18, decimal_places=2, default=0)
    is_active = models.BooleanField("เปิดใช้งาน", default=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "ออปชันสินค้า"
        verbose_name_plural = "ออปชันสินค้า"

    def __str__(self) -> str:
        return self.name


class BundleItem(TenantScopedModel):
    """A component inside a bundle product (e.g. a 'ชุดโต๊ะประชุม' contains a table + N chairs)."""

    bundle = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="bundle_items")
    component = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    quantity = models.DecimalField("จำนวน", max_digits=12, decimal_places=2, default=1)

    class Meta:
        verbose_name = "รายการในชุด"
        verbose_name_plural = "รายการในชุด"

    def __str__(self) -> str:
        return f"{self.component} × {self.quantity}"
