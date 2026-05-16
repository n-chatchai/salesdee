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
    SALES_ORDER = "sales_order", "ใบสั่งขาย"
    DELIVERY_NOTE = "delivery_note", "ใบส่งของ"
    INVOICE = "invoice", "ใบแจ้งหนี้/ใบวางบิล"
    TAX_INVOICE = "tax_invoice", "ใบกำกับภาษี"
    RECEIPT = "receipt", "ใบเสร็จรับเงิน"
    CREDIT_NOTE = "credit_note", "ใบลดหนี้"
    DEBIT_NOTE = "debit_note", "ใบเพิ่มหนี้"
    DEPOSIT = "deposit", "ใบรับเงินมัดจำ"


# Doc types that, once they carry a number, are immutable tax/legal documents (CLAUDE.md §4.3/§4.4).
LOCKED_DOC_TYPES = frozenset(
    {DocType.TAX_INVOICE, DocType.CREDIT_NOTE, DocType.DEBIT_NOTE, DocType.RECEIPT}
)


class DocStatus(models.TextChoices):
    REQUEST = "request", "คำขอจากลูกค้า"  # pre-quote: arrived via Path A web form
    DRAFT = "draft", "ร่าง"
    PENDING_APPROVAL = "pending", "รออนุมัติ"
    READY = "ready", "พร้อมส่ง"
    SENT = "sent", "ส่งให้ลูกค้าแล้ว"
    ACCEPTED = "accepted", "ลูกค้าตอบรับ"
    REJECTED = "rejected", "ลูกค้าปฏิเสธ"
    EXPIRED = "expired", "หมดอายุ"
    CANCELLED = "cancelled", "ยกเลิก"


class DocSource(models.TextChoices):
    """Where this document originated · drives the queue source-badge + filter."""

    MANUAL = "manual", "สร้างเอง"
    LINE = "line", "ไลน์"
    WEBSITE = "website", "เว็บไซต์"
    EMAIL = "email", "อีเมล"


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
    revision_note = models.CharField(
        "เหตุผลของการแก้ไขล่าสุด",
        max_length=255,
        blank=True,
        help_text="ใส่ตอนกด “เปิดแก้ไขใหม่”; จะถูกบันทึกลงในเวอร์ชันถัดไปที่ส่ง",
    )
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
    due_date = models.DateField("ครบกำหนดชำระ", null=True, blank=True)
    issued_at = models.DateTimeField("ออกเอกสารเมื่อ", null=True, blank=True)
    # What this document was converted/derived from (quotation → invoice → tax invoice → receipt).
    source_document = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="derived_documents",
        null=True,
        blank=True,
    )
    # For a credit/debit note: the tax invoice it adjusts (Revenue Code §86/9–86/10).
    references_document = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="referencing_documents",
        null=True,
        blank=True,
    )
    cancelled_reason = models.CharField("เหตุผลการยกเลิก", max_length=255, blank=True)
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
    # Where this doc originated (drives queue source-badge + Quote Requests filter). For LINE-
    # sourced docs `source_conversation` still points to the thread; `source` is the high-level
    # bucket. New rows default to MANUAL; web/intake/LINE flows set this explicitly.
    source = models.CharField(
        "ที่มา", max_length=10, choices=DocSource.choices, default=DocSource.MANUAL, db_index=True
    )
    # If the quotation was drafted from a LINE conversation (Quote-from-Chat), the source thread —
    # so sending it can post the Flex summary back into that chat and the deal shows the open count.
    source_conversation = models.ForeignKey(
        "integrations.Conversation",
        on_delete=models.SET_NULL,
        related_name="quotations",
        null=True,
        blank=True,
    )
    # Customer-opened-the-public-link tracking (REQUIREMENTS.md §4.8; the "เปิด N ครั้ง" signal).
    first_viewed_at = models.DateTimeField("ลูกค้าเปิดดูครั้งแรก", null=True, blank=True)
    last_viewed_at = models.DateTimeField("ลูกค้าเปิดดูล่าสุด", null=True, blank=True)
    view_count = models.PositiveIntegerField("จำนวนครั้งที่เปิดดู", default=0)
    # Discount approval (REQUIREMENTS.md §4.7) — set when a manager/owner approves a quotation
    # whose discount exceeds the salesperson's cap (apps.quotes.services.submit_quotation).
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    approved_at = models.DateTimeField("อนุมัติเมื่อ", null=True, blank=True)
    # Customer response captured via the public share link
    customer_response = models.CharField(
        "การตอบกลับของลูกค้า", max_length=10, choices=CustomerResponse.choices, blank=True
    )
    customer_signed_name = models.CharField("ลงชื่อโดย", max_length=200, blank=True)
    customer_response_note = models.TextField("ข้อความจากลูกค้า", blank=True)
    customer_responded_at = models.DateTimeField("ตอบกลับเมื่อ", null=True, blank=True)
    customer_response_ip = models.GenericIPAddressField("IP ที่ตอบกลับ", null=True, blank=True)

    # Statuses in which the document content (header + lines) may still be edited. Once SENT it's
    # locked; changing it means reopening to a new revision (apps.quotes.services.reopen_quotation).
    EDITABLE_STATUSES = (DocStatus.DRAFT, DocStatus.PENDING_APPROVAL, DocStatus.READY)
    # Terminal-ish statuses from which "reopen for changes" makes sense.
    REOPENABLE_STATUSES = (
        DocStatus.SENT,
        DocStatus.ACCEPTED,
        DocStatus.REJECTED,
        DocStatus.EXPIRED,
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "เอกสารขาย"
        verbose_name_plural = "เอกสารขาย"
        indexes = [models.Index(fields=["tenant", "doc_type", "status"])]

    def __str__(self) -> str:
        return self.doc_number or f"(ร่าง) {self.get_doc_type_display()} #{self.pk}"

    @property
    def is_locked_tax_document(self) -> bool:
        """A tax/legal document (tax invoice, credit/debit note, receipt) that has been issued —
        i.e. carries a number. Such documents are immutable (CLAUDE.md §4.4)."""
        return self.doc_type in LOCKED_DOC_TYPES and bool(self.doc_number)

    @property
    def is_editable(self) -> bool:
        if self.is_locked_tax_document:
            return False
        return self.status in self.EDITABLE_STATUSES

    def save(self, *args, **kwargs):
        if self.pk is not None and self.doc_type in LOCKED_DOC_TYPES:
            # An already-issued tax doc (has a number persisted) is immutable except for the
            # cancellation fields (CLAUDE.md §4.4).
            issued = type(self).all_tenants.filter(pk=self.pk).exclude(doc_number="").exists()
            if issued:
                update_fields = kwargs.get("update_fields")
                allowed = {"status", "cancelled_reason", "updated_at"}
                if update_fields is None or not set(update_fields).issubset(allowed):
                    from apps.quotes.services import WorkflowError

                    raise WorkflowError("เอกสารภาษีที่ออกแล้วแก้ไขไม่ได้ — ต้องออกใบลดหนี้/ใบเพิ่มหนี้แทน")
        super().save(*args, **kwargs)


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


class QuotationRevision(TenantScopedModel):
    """A frozen snapshot of a quotation as it was sent (REQUIREMENTS.md §4.7 FR-7.20).

    Taken when the document moves READY → SENT. ``snapshot`` is a self-contained JSON copy of the
    header + lines + computed totals at that moment; old revisions stay viewable/diff-able even after
    the live document is reopened and changed.
    """

    document = models.ForeignKey(SalesDocument, on_delete=models.CASCADE, related_name="revisions")
    revision = models.PositiveIntegerField("เลขที่แก้ไข (Rev.)")
    snapshot = models.JSONField("ข้อมูล ณ ตอนส่ง")
    reason = models.CharField("เหตุผลที่แก้ไข", max_length=255, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )

    class Meta:
        ordering = ("document", "revision")
        verbose_name = "เวอร์ชันใบเสนอราคา"
        verbose_name_plural = "เวอร์ชันใบเสนอราคา"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "revision"], name="uniq_quote_revision_per_doc"
            )
        ]

    def __str__(self) -> str:
        return f"{self.document} Rev.{self.revision}"
