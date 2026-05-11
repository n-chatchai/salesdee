"""Quotations (and, later, the rest of the sales-document chain). Spec: REQUIREMENTS.md §4.7–§4.8.

Round 1: SalesDocument(docType=QUOTATION) + SalesDocLine + per-tenant document-number sequences.
Totals are computed on the fly (apps.quotes.services.compute_document_totals); for issued/sent
documents this should later be snapshotted (revisions — round 2).
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.catalog.models import TaxType
from apps.core.models import BaseModel, TenantScopedModel


class DocType(models.TextChoices):
    QUOTATION = "quotation", "ใบเสนอราคา"
    # phase 2: SALES_ORDER, DELIVERY_NOTE, INVOICE, TAX_INVOICE, RECEIPT, CREDIT_NOTE, DEBIT_NOTE, DEPOSIT


class DocStatus(models.TextChoices):
    DRAFT = "draft", "ร่าง"
    PENDING_APPROVAL = "pending", "รออนุมัติ"
    READY = "ready", "พร้อมส่ง"
    SENT = "sent", "ส่งให้ลูกค้าแล้ว"
    ACCEPTED = "accepted", "ลูกค้าตอบรับ"
    REJECTED = "rejected", "ลูกค้าปฏิเสธ"
    EXPIRED = "expired", "หมดอายุ"
    CANCELLED = "cancelled", "ยกเลิก"


class PriceMode(models.TextChoices):
    EXCLUSIVE = "excl", "ราคาไม่รวม VAT"
    INCLUSIVE = "incl", "ราคารวม VAT แล้ว"


class DiscountKind(models.TextChoices):
    AMOUNT = "amount", "บาท"
    PERCENT = "percent", "%"


class LineType(models.TextChoices):
    ITEM = "item", "รายการ"
    HEADING = "heading", "หัวข้อ/กลุ่ม"
    NOTE = "note", "ข้อความ"


class CustomerResponse(models.TextChoices):
    ACCEPTED = "accepted", "ยอมรับ"
    CHANGES = "changes", "ขอแก้ไข"
    REJECTED = "rejected", "ปฏิเสธ"


class DocumentNumberSequence(TenantScopedModel):
    """One running counter per (tenant, doc_type, year). Allocate via apps.quotes.services."""

    doc_type = models.CharField(max_length=20, choices=DocType.choices)
    year = models.PositiveIntegerField(help_text="ปีของเลขที่เอกสาร (พ.ศ.)")
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "ลำดับเลขที่เอกสาร"
        verbose_name_plural = "ลำดับเลขที่เอกสาร"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "doc_type", "year"], name="uniq_docseq_per_tenant"
            )
        ]

    def __str__(self) -> str:
        return f"{self.doc_type} {self.year}: {self.last_number}"


class SalesDocument(TenantScopedModel):
    doc_type = models.CharField(
        "ชนิดเอกสาร", max_length=20, choices=DocType.choices, default=DocType.QUOTATION
    )
    doc_number = models.CharField("เลขที่เอกสาร", max_length=40, blank=True, db_index=True)
    revision = models.PositiveIntegerField("เลขที่แก้ไข (Rev.)", default=0)
    deal = models.ForeignKey(
        "crm.Deal", on_delete=models.SET_NULL, related_name="documents", null=True, blank=True
    )
    customer = models.ForeignKey(
        "crm.Customer", on_delete=models.PROTECT, related_name="documents", null=True, blank=True
    )
    contact = models.ForeignKey(
        "crm.Contact", on_delete=models.SET_NULL, related_name="documents", null=True, blank=True
    )
    issue_date = models.DateField("วันที่ออก")
    valid_until = models.DateField("ยืนราคาถึง", null=True, blank=True)
    reference = models.CharField(
        "อ้างอิง", max_length=255, blank=True, help_text="เช่น ชื่อโครงการ / RFQ ของลูกค้า"
    )
    salesperson = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="sales_documents",
        null=True,
        blank=True,
    )
    currency = models.CharField("สกุลเงิน", max_length=3, default="THB")
    price_mode = models.CharField(
        "รูปแบบราคา", max_length=4, choices=PriceMode.choices, default=PriceMode.EXCLUSIVE
    )
    status = models.CharField(
        "สถานะ", max_length=10, choices=DocStatus.choices, default=DocStatus.DRAFT
    )
    end_discount_kind = models.CharField(
        "ชนิดส่วนลดท้ายบิล", max_length=10, choices=DiscountKind.choices, default=DiscountKind.AMOUNT
    )
    end_discount_value = models.DecimalField(
        "ส่วนลดท้ายบิล", max_digits=18, decimal_places=4, default=0
    )
    payment_terms = models.TextField("เงื่อนไขการชำระเงิน", blank=True)
    lead_time = models.CharField("กำหนดส่งมอบ/ติดตั้ง", max_length=255, blank=True)
    warranty = models.CharField("การรับประกัน", max_length=255, blank=True)
    notes = models.TextField("หมายเหตุ/เงื่อนไขอื่น", blank=True)
    bank_account = models.ForeignKey(
        "tenants.BankAccount", on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    sent_at = models.DateTimeField("ส่งให้ลูกค้าเมื่อ", null=True, blank=True)
    # Customer response captured via the public share link
    customer_response = models.CharField(
        "การตอบกลับของลูกค้า", max_length=10, choices=CustomerResponse.choices, blank=True
    )
    customer_signed_name = models.CharField("ลงชื่อโดย", max_length=200, blank=True)
    customer_response_note = models.TextField("ข้อความจากลูกค้า", blank=True)
    customer_responded_at = models.DateTimeField("ตอบกลับเมื่อ", null=True, blank=True)
    customer_response_ip = models.GenericIPAddressField("IP ที่ตอบกลับ", null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "เอกสารขาย"
        verbose_name_plural = "เอกสารขาย"
        indexes = [models.Index(fields=["tenant", "doc_type", "status"])]

    def __str__(self) -> str:
        return self.doc_number or f"(ร่าง) {self.get_doc_type_display()} #{self.pk}"


class SalesDocLine(TenantScopedModel):
    document = models.ForeignKey(SalesDocument, on_delete=models.CASCADE, related_name="lines")
    group_label = models.CharField("ห้อง/โซน", max_length=120, blank=True)
    position = models.PositiveIntegerField("ลำดับ", default=0)
    line_type = models.CharField(
        "ชนิดบรรทัด", max_length=10, choices=LineType.choices, default=LineType.ITEM
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    description = models.TextField("รายละเอียด", blank=True)
    dimensions = models.CharField("ขนาด W×D×H", max_length=120, blank=True)
    material = models.CharField("วัสดุ/สี", max_length=255, blank=True)
    image = models.ImageField("รูปประกอบ", upload_to="quote_lines/", null=True, blank=True)
    quantity = models.DecimalField("จำนวน", max_digits=14, decimal_places=2, default=1)
    unit = models.CharField("หน่วย", max_length=30, default="ชิ้น")
    unit_price = models.DecimalField("ราคา/หน่วย", max_digits=18, decimal_places=2, default=0)
    discount_kind = models.CharField(
        "ชนิดส่วนลด", max_length=10, choices=DiscountKind.choices, default=DiscountKind.AMOUNT
    )
    discount_value = models.DecimalField("ส่วนลด", max_digits=18, decimal_places=4, default=0)
    tax_type = models.CharField("ภาษี", max_length=10, choices=TaxType.choices, default=TaxType.VAT7)
    withholding_rate = models.DecimalField(
        "หัก ณ ที่จ่าย (%)", max_digits=5, decimal_places=2, default=0
    )

    class Meta:
        ordering = ("position", "id")
        verbose_name = "บรรทัดในเอกสาร"
        verbose_name_plural = "บรรทัดในเอกสาร"

    def __str__(self) -> str:
        return self.description[:60] or self.get_line_type_display()

    @property
    def line_discount(self) -> Decimal:
        base = Decimal(self.quantity) * Decimal(self.unit_price)
        if self.discount_kind == DiscountKind.PERCENT:
            return base * Decimal(self.discount_value) / 100
        return Decimal(self.discount_value)

    @property
    def amount(self) -> Decimal:
        """Net line amount (qty × price − discount). Ignored in totals for HEADING/NOTE lines."""
        return Decimal(self.quantity) * Decimal(self.unit_price) - self.line_discount


class QuotationShareLink(BaseModel):
    """A tokenized public link to view/accept a quotation (no login). Global model — it resolves
    the tenant from the token, so it's looked up before any tenant context (no RLS), like TenantDomain."""

    tenant = models.ForeignKey(
        "tenants.Tenant", on_delete=models.CASCADE, related_name="quote_share_links"
    )
    document = models.ForeignKey(
        SalesDocument, on_delete=models.CASCADE, related_name="share_links"
    )
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )

    class Meta:
        verbose_name = "ลิงก์แชร์ใบเสนอราคา"
        verbose_name_plural = "ลิงก์แชร์ใบเสนอราคา"

    def __str__(self) -> str:
        return f"link {self.token[:8]}… -> {self.document}"

    def is_valid(self) -> bool:
        from django.utils import timezone

        return not self.revoked and (self.expires_at is None or self.expires_at > timezone.now())
