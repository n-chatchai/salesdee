"""Billing & accounts receivable (REQUIREMENTS.md §4.13–§4.14.1).

Documents (invoices, tax invoices, receipts, credit/debit notes) all live on
``apps.quotes.models.SalesDocument`` — this app only adds *payments* and their allocation to
invoices, plus AR/sales-tax reporting in ``services.py``.

Invariants (CLAUDE.md §4): issued tax documents are immutable; tax-document numbers are gap-free;
money is ``Decimal``; rates are snapshotted onto the document.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TenantScopedModel


class PaymentMethod(models.TextChoices):
    CASH = "cash", "เงินสด"
    TRANSFER = "transfer", "โอนเงิน"
    CHEQUE = "cheque", "เช็ค"
    CARD = "card", "บัตรเครดิต/เดบิต"
    OTHER = "other", "อื่นๆ"


class PaymentStatus(models.TextChoices):
    RECORDED = "recorded", "บันทึกแล้ว"
    CLEARED = "cleared", "เคลียร์แล้ว"
    BOUNCED = "bounced", "เช็คคืน"


class Payment(TenantScopedModel):
    """Money received from a customer, allocated to one or more invoices (``PaymentAllocation``)."""

    customer = models.ForeignKey("crm.Customer", on_delete=models.PROTECT, related_name="payments")
    date = models.DateField("วันที่รับชำระ")
    method = models.CharField(
        "วิธีชำระ", max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.TRANSFER
    )
    bank_account = models.ForeignKey(
        "tenants.BankAccount", on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    gross_amount = models.DecimalField("จำนวนเงินที่รับ", max_digits=18, decimal_places=2)
    fee = models.DecimalField("ค่าธรรมเนียม", max_digits=18, decimal_places=2, default=0)
    withholding_deducted = models.DecimalField(
        "ภาษีหัก ณ ที่จ่ายที่ลูกค้าหักไว้", max_digits=18, decimal_places=2, default=0
    )
    withholding_cert_ref = models.CharField("เลขที่หนังสือรับรองการหักภาษี", max_length=120, blank=True)
    reference = models.CharField("อ้างอิง (เลขที่เช็ค/สลิป)", max_length=200, blank=True)
    receipt_document = models.ForeignKey(
        "quotes.SalesDocument", on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )
    status = models.CharField(
        "สถานะ", max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.RECORDED
    )
    notes = models.TextField("หมายเหตุ", blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="+", null=True, blank=True
    )

    class Meta:
        ordering = ("-date", "-created_at")
        verbose_name = "การรับชำระเงิน"
        verbose_name_plural = "การรับชำระเงิน"

    def __str__(self) -> str:
        return f"รับชำระ {self.gross_amount} ({self.customer})"


class PaymentAllocation(TenantScopedModel):
    """How much of a ``Payment`` is applied to a given invoice (``SalesDocument`` of type INVOICE)."""

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="allocations")
    invoice = models.ForeignKey(
        "quotes.SalesDocument", on_delete=models.PROTECT, related_name="payment_allocations"
    )
    amount = models.DecimalField("จำนวนที่ตัดชำระ", max_digits=18, decimal_places=2)

    class Meta:
        verbose_name = "การตัดชำระ"
        verbose_name_plural = "การตัดชำระ"

    def __str__(self) -> str:
        return f"{self.amount} -> {self.invoice}"
