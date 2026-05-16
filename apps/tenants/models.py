from __future__ import annotations

from django.db import models
from django.utils.text import slugify

from apps.core.models import BaseModel, TenantScopedModel


class Plan(models.TextChoices):
    FREE = "free", "Free"
    STARTER = "starter", "Starter"
    GROWTH = "growth", "Growth"
    PRO = "pro", "Pro"
    BUSINESS = "business", "Business"


class BillingCycle(models.TextChoices):
    MONTHLY = "monthly", "รายเดือน"
    ANNUAL = "annual", "รายปี"


class Tenant(BaseModel):
    """A workspace = one customer business. The unit of data isolation (CLAUDE.md §5).

    Global model (not TenantScopedModel) — it *is* the tenant.
    """

    name = models.CharField("ชื่อธุรกิจ", max_length=200)
    slug = models.SlugField(
        max_length=63, unique=True, help_text="ใช้เป็น subdomain: <slug>.<APP_DOMAIN>"
    )
    is_active = models.BooleanField("เปิดใช้งาน", default=True)
    plan = models.CharField("แพ็กเกจ", max_length=20, choices=Plan.choices, default=Plan.FREE)
    billing_cycle = models.CharField(
        "รอบบิล", max_length=20, choices=BillingCycle.choices, default=BillingCycle.MONTHLY
    )
    trial_ends_at = models.DateField("วันสิ้นสุดทดลองใช้", null=True, blank=True)
    subscription_started_at = models.DateField("วันเริ่มแพ็กเกจ", null=True, blank=True)
    current_period_ends_at = models.DateField("รอบปัจจุบันสิ้นสุด", null=True, blank=True)

    THEMES = (
        ("craft", "Craft · warm classic"),
        ("atelier", "Atelier · refined"),
        ("bauhaus", "Bauhaus · bold modern"),
        ("velvet", "Velvet · luxe dark"),
    )
    theme = models.CharField(
        "ธีมเว็บ tenant", max_length=20, choices=THEMES, default="craft", db_index=True
    )

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


class FeatureOverrideMode(models.TextChoices):
    FORCE_ON = "on", "บังคับเปิด"
    FORCE_OFF = "off", "บังคับปิด"


class TenantFeatureOverride(BaseModel):
    """Platform-admin override of a plan-gated module for a specific tenant.

    Use sparingly — most "this customer is special" cases should be handled by giving them a
    higher plan via ``Tenant.plan``. Overrides exist for narrow cases:
    - granting an anchor customer a feature for free during onboarding (FORCE_ON + expires_at)
    - disabling a feature for a tenant in dispute or violation (FORCE_OFF)
    - rolling out a beta feature to early adopters before raising it to the plan

    Global model (not TenantScopedModel) — only platform admins (Django superusers) manage these
    via ``/admin/tenants/tenantfeatureoverride/``. Tenant members never see or edit them.
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="feature_overrides")
    module_code = models.CharField(
        "รหัสโมดูล",
        max_length=64,
        help_text="เช่น billing, e_tax, white_label, custom_domain, api, priority_support, sla",
    )
    mode = models.CharField(
        "โหมด",
        max_length=10,
        choices=FeatureOverrideMode.choices,
        default=FeatureOverrideMode.FORCE_ON,
    )
    reason = models.TextField("เหตุผล", help_text="ลูกค้า anchor, รางวัล, รอ release ฯลฯ")
    expires_at = models.DateField("หมดอายุ", null=True, blank=True, help_text="เว้นว่าง = ถาวร")

    class Meta:
        verbose_name = "การ override โมดูล"
        verbose_name_plural = "การ override โมดูล"
        unique_together = (("tenant", "module_code"),)
        ordering = ("tenant", "module_code")

    def __str__(self) -> str:
        return f"{self.tenant.slug}: {self.module_code} → {self.get_mode_display()}"

    @property
    def is_active(self) -> bool:
        if self.expires_at is None:
            return True
        from datetime import date

        return self.expires_at >= date.today()


class Usage(TenantScopedModel):
    """Monthly usage counter, one row per (tenant, period, kind) — bumped by `quota.increment_usage`.

    ``period`` is YYYYMM (Asia/Bangkok local month — see ``quota.current_period``). ``kind`` is
    one of ``apps.tenants.plans.USAGE_KINDS``. The cap is read from the tenant's plan; this row
    only tracks the counter, never the cap (which is config, not data).
    """

    period = models.PositiveIntegerField("รอบเดือน (YYYYMM)")
    kind = models.CharField("ประเภท", max_length=32)
    count = models.PositiveIntegerField("จำนวน", default=0)

    class Meta:
        verbose_name = "การใช้งาน"
        verbose_name_plural = "การใช้งาน"
        unique_together = (("tenant", "period", "kind"),)
        indexes = [models.Index(fields=("tenant", "period"))]

    def __str__(self) -> str:
        return f"{self.tenant_id}/{self.period}/{self.kind}={self.count}"


class QuoteTemplate(BaseModel):
    """Per-tenant default values for every quotation · drives header text, terms, layout.
    Settings page (h.2) lets the owner edit once · every new quote inherits these. Sales
    can override per-document. OneToOne · auto-created on first access."""

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="quote_template")
    title_text = models.CharField(
        "ข้อความหัวเอกสาร", max_length=200, default="ใบเสนอราคา / QUOTATION"
    )
    delivery_days = models.PositiveIntegerField("กำหนดส่งของ (วัน)", default=45)
    validity_days = models.PositiveIntegerField("ยืนราคา (วัน)", default=90)
    payment_terms = models.TextField(
        "เงื่อนไขการชำระเงิน", blank=True,
        default="โอนเข้าบัญชีธนาคารหลัก · ส่งสลิปยืนยันการโอน",
    )
    deposit_text = models.CharField(
        "ชำระล่วงหน้า (deposit)", max_length=200, default="30% ก่อนเริ่มงาน", blank=True
    )
    after_delivery_text = models.CharField(
        "ชำระหลังส่งมอบ", max_length=200, default="70% เมื่อรับมอบงาน", blank=True
    )
    warranty_text = models.CharField(
        "การรับประกัน", max_length=200, default="1 ปี จากการใช้งานปกติ", blank=True
    )
    signer_name = models.CharField("ชื่อผู้ลงนาม", max_length=200, blank=True)
    signer_phone = models.CharField("เบอร์ผู้ลงนาม", max_length=40, blank=True)
    vat_enabled = models.BooleanField("เปิด VAT 7%", default=True)
    wht_enabled = models.BooleanField("เปิด WHT 3% (หัก ณ ที่จ่าย)", default=False)
    PAGE2_LAYOUTS = (
        ("none", "ไม่มีหน้ารูป"),
        ("one", "1 รายการ/หน้า · รูปใหญ่"),
        ("two", "2 รายการ/หน้า"),
        ("grid4", "Grid 4 รายการ/หน้า"),
    )
    page2_layout = models.CharField(
        "หน้ารูปสินค้า · เลย์เอาต์", max_length=10, choices=PAGE2_LAYOUTS, default="one"
    )

    class Meta:
        verbose_name = "เทมเพลตใบเสนอราคา"
        verbose_name_plural = "เทมเพลตใบเสนอราคา"

    def __str__(self) -> str:
        return f"QuoteTemplate · {self.tenant.slug}"


class HeroBanner(TenantScopedModel):
    """Hero banner shown on the tenant's public landing page (frame a · i.1 CMS).
    Tenant CMS adds / reorders / toggles banners. Public site renders first `is_active=True`
    by `order`. Image is required; headline + cta optional."""

    headline = models.CharField("หัวข้อ", max_length=200, blank=True)
    subline = models.CharField("รายละเอียด", max_length=300, blank=True)
    image = models.ImageField("ภาพ", upload_to="hero_banners/")
    cta_label = models.CharField("ข้อความปุ่ม", max_length=80, blank=True)
    cta_url = models.URLField("ปุ่มลิงก์ไปที่", blank=True)
    order = models.PositiveIntegerField("ลำดับ", default=0, db_index=True)
    is_active = models.BooleanField("เปิดใช้", default=True)

    class Meta:
        verbose_name = "Hero banner"
        verbose_name_plural = "Hero banners"
        ordering = ("order", "-created_at")

    def __str__(self) -> str:
        return self.headline or f"banner #{self.pk}"


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
