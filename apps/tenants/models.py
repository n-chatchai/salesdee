from __future__ import annotations

from django.db import models
from django.utils.text import slugify

from apps.core.models import BaseModel, TenantScopedModel


class Plan(models.TextChoices):
    TRIAL = "trial", "ทดลองใช้"
    STARTER = "starter", "Starter"
    PRO = "pro", "Pro"
    BUSINESS = "business", "Business"
    ENTERPRISE = "enterprise", "Enterprise"


class Tenant(BaseModel):
    """A workspace = one customer business. The unit of data isolation (CLAUDE.md §5).

    Global model (not TenantScopedModel) — it *is* the tenant.
    """

    name = models.CharField("ชื่อธุรกิจ", max_length=200)
    slug = models.SlugField(
        max_length=63, unique=True, help_text="ใช้เป็น subdomain: <slug>.<APP_DOMAIN>"
    )
    is_active = models.BooleanField("เปิดใช้งาน", default=True)
    plan = models.CharField("แพ็กเกจ", max_length=20, choices=Plan.choices, default=Plan.TRIAL)
    trial_ends_at = models.DateField("วันสิ้นสุดทดลองใช้", null=True, blank=True)

    class Meta:
        verbose_name = "Workspace"
        verbose_name_plural = "Workspaces"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:63] or "tenant"
        super().save(*args, **kwargs)


class TenantDomain(BaseModel):
    """A hostname that maps to a tenant. Used for custom domains (e.g. crm.wandeedee.com)
    in addition to the built-in `<slug>.<APP_DOMAIN>` subdomain.

    Global model — it's the thing that *resolves* the tenant from the request host, so it's
    looked up before any tenant context exists. Not RLS-protected (it's routing metadata).
    DNS + on-demand TLS for the domain are a deployment concern (see CLAUDE.md §5 / NEXT_STEPS).
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="domains")
    domain = models.CharField(
        "โดเมน", max_length=253, unique=True, help_text="เช่น crm.example.com (ไม่ใส่ http://)"
    )
    is_primary = models.BooleanField("โดเมนหลัก", default=False)
    verified = models.BooleanField("ยืนยันความเป็นเจ้าของแล้ว", default=False)

    class Meta:
        verbose_name = "Custom domain"
        verbose_name_plural = "Custom domains"
        ordering = ("-is_primary", "domain")

    def __str__(self) -> str:
        return self.domain

    def save(self, *args, **kwargs):
        self.domain = self.domain.strip().lower()
        super().save(*args, **kwargs)


class Branch(models.TextChoices):
    HEAD_OFFICE = "head", "สำนักงานใหญ่"
    BRANCH = "branch", "สาขา"


class CompanyProfile(BaseModel):
    """The tenant's company header info — used on every document (REQUIREMENTS.md §4.1, §5.2)."""

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="company_profile")
    name_th = models.CharField("ชื่อบริษัท (ไทย)", max_length=255)
    name_en = models.CharField("ชื่อบริษัท (อังกฤษ)", max_length=255, blank=True)
    tax_id = models.CharField("เลขประจำตัวผู้เสียภาษี (13 หลัก)", max_length=13, blank=True)
    branch_kind = models.CharField(
        "ประเภทสำนักงาน", max_length=10, choices=Branch.choices, default=Branch.HEAD_OFFICE
    )
    branch_code = models.CharField(
        "รหัสสาขา (ถ้ามี)", max_length=10, blank=True, help_text="เช่น 00001"
    )
    address = models.TextField("ที่อยู่", blank=True)
    phone = models.CharField("โทรศัพท์", max_length=50, blank=True)
    email = models.EmailField("อีเมล", blank=True)
    website = models.URLField("เว็บไซต์", blank=True)
    line_id = models.CharField("LINE", max_length=100, blank=True)
    logo = models.ImageField("โลโก้", upload_to="company_logos/", blank=True, null=True)

    class Meta:
        verbose_name = "ข้อมูลบริษัท"
        verbose_name_plural = "ข้อมูลบริษัท"

    def __str__(self) -> str:
        return self.name_th

    @property
    def branch_label(self) -> str:
        """e.g. 'สำนักงานใหญ่' or 'สาขาที่ 00001'."""
        if self.branch_kind == Branch.HEAD_OFFICE:
            return "สำนักงานใหญ่"
        return f"สาขาที่ {self.branch_code}".strip()


class BankAccount(TenantScopedModel):
    """A bank account of the tenant, shown in payment terms on documents (REQUIREMENTS.md §4.1)."""

    bank_name = models.CharField("ธนาคาร", max_length=100)
    branch_name = models.CharField("สาขา", max_length=100, blank=True)
    account_name = models.CharField("ชื่อบัญชี", max_length=200)
    account_number = models.CharField("เลขที่บัญชี", max_length=30)
    account_type = models.CharField(
        "ประเภทบัญชี", max_length=50, blank=True, help_text="เช่น ออมทรัพย์ / กระแสรายวัน"
    )
    is_default = models.BooleanField("บัญชีหลัก", default=False)

    class Meta:
        verbose_name = "บัญชีธนาคาร"
        verbose_name_plural = "บัญชีธนาคาร"
        ordering = ("-is_default", "bank_name")

    def __str__(self) -> str:
        return f"{self.bank_name} {self.account_number}"
