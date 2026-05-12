"""CRM domain — customers/contacts master + leads/deals/pipeline + activities/tasks.
Spec: REQUIREMENTS.md §4.2–§4.5. All models are tenant-owned (``TenantScopedModel``).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TenantScopedModel


# --- Customers & contacts -----------------------------------------------------
class CustomerKind(models.TextChoices):
    COMPANY = "company", "นิติบุคคล"
    INDIVIDUAL = "individual", "บุคคลธรรมดา"


class Customer(TenantScopedModel):
    name = models.CharField("ชื่อลูกค้า", max_length=255)
    name_en = models.CharField("ชื่อ (อังกฤษ)", max_length=255, blank=True)
    kind = models.CharField(
        "ประเภท", max_length=20, choices=CustomerKind.choices, default=CustomerKind.COMPANY
    )
    tax_id = models.CharField("เลขประจำตัวผู้เสียภาษี", max_length=20, blank=True)
    branch_label = models.CharField(
        "สำนักงาน/สาขา", max_length=50, blank=True, help_text='เช่น "สำนักงานใหญ่" หรือ "สาขาที่ 00001"'
    )
    billing_address = models.TextField("ที่อยู่ออกใบกำกับภาษี", blank=True)
    shipping_address = models.TextField("ที่อยู่จัดส่ง/หน้างาน", blank=True)
    default_credit_days = models.PositiveIntegerField("เครดิตเริ่มต้น (วัน)", default=0)
    notes = models.TextField("หมายเหตุ", blank=True)
    is_archived = models.BooleanField("เก็บเข้าคลัง", default=False)

    class Meta:
        ordering = ("name",)
        verbose_name = "ลูกค้า"
        verbose_name_plural = "ลูกค้า"
        indexes = [models.Index(fields=["tenant", "name"])]

    def __str__(self) -> str:
        return self.name


class Contact(TenantScopedModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField("ชื่อ-นามสกุล", max_length=200)
    title = models.CharField("ตำแหน่ง", max_length=150, blank=True)
    department = models.CharField("แผนก", max_length=150, blank=True)
    phone = models.CharField("โทรศัพท์", max_length=50, blank=True)
    email = models.EmailField("อีเมล", blank=True)
    line_id = models.CharField("LINE", max_length=100, blank=True)
    is_primary = models.BooleanField("ผู้ติดต่อหลัก", default=False)

    class Meta:
        ordering = ("-is_primary", "name")
        verbose_name = "ผู้ติดต่อ"
        verbose_name_plural = "ผู้ติดต่อ"

    def __str__(self) -> str:
        return self.name


# --- Pipeline & deals ---------------------------------------------------------
class StageKind(models.TextChoices):
    OPEN = "open", "กำลังดำเนินการ"
    WON = "won", "ปิดได้"
    LOST = "lost", "ปิดไม่ได้"


class PipelineStage(TenantScopedModel):
    name = models.CharField("ชื่อขั้น", max_length=100)
    order = models.PositiveIntegerField("ลำดับ", default=0)
    kind = models.CharField(
        "ประเภท", max_length=10, choices=StageKind.choices, default=StageKind.OPEN
    )
    default_probability = models.PositiveSmallIntegerField(
        "โอกาสปิด (%)", default=0, help_text="0–100"
    )

    class Meta:
        ordering = ("order", "id")
        verbose_name = "ขั้นใน Pipeline"
        verbose_name_plural = "ขั้นใน Pipeline"

    def __str__(self) -> str:
        return self.name


class LeadChannel(models.TextChoices):
    LINE = "line", "LINE"
    FACEBOOK = "facebook", "Facebook/Messenger"
    PHONE = "phone", "โทรศัพท์"
    WEB_FORM = "web_form", "ฟอร์มเว็บไซต์"
    EMAIL = "email", "อีเมล"
    WALK_IN = "walk_in", "Walk-in / โชว์รูม"
    EXHIBITION = "exhibition", "ออกบูธ/งานแฟร์"
    EBIDDING = "ebidding", "e-Bidding ภาครัฐ"
    REFERRAL = "referral", "แนะนำต่อ"
    OTHER = "other", "อื่น ๆ"


class DealStatus(models.TextChoices):
    OPEN = "open", "เปิดอยู่"
    WON = "won", "ปิดได้"
    LOST = "lost", "ปิดไม่ได้"


class Deal(TenantScopedModel):
    name = models.CharField("ชื่อดีล/โครงการ", max_length=255)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="deals", null=True, blank=True
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, related_name="deals", null=True, blank=True
    )
    # nullable for now — new tenants get default stages once tenant onboarding seeds them.
    stage = models.ForeignKey(
        PipelineStage, on_delete=models.PROTECT, related_name="deals", null=True, blank=True
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="owned_deals",
        null=True,
        blank=True,
    )
    estimated_value = models.DecimalField(
        "มูลค่าโดยประมาณ", max_digits=18, decimal_places=2, default=0
    )
    probability = models.PositiveSmallIntegerField("โอกาสปิด (%)", default=0)
    expected_close_date = models.DateField("คาดปิดวันที่", null=True, blank=True)
    channel = models.CharField("ช่องทาง", max_length=20, choices=LeadChannel.choices, blank=True)
    source = models.CharField(
        "แหล่งที่มา", max_length=255, blank=True, help_text="เช่น ชื่อแคมเปญ / ผู้แนะนำ"
    )
    status = models.CharField(
        "สถานะ", max_length=10, choices=DealStatus.choices, default=DealStatus.OPEN
    )
    lost_reason = models.CharField("เหตุผลที่แพ้", max_length=255, blank=True)
    notes = models.TextField("หมายเหตุ", blank=True)
    closed_at = models.DateTimeField("ปิดเมื่อ", null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "ดีล"
        verbose_name_plural = "ดีล"
        indexes = [models.Index(fields=["tenant", "status", "stage"])]

    def __str__(self) -> str:
        return self.name


# --- Activities & tasks -------------------------------------------------------
class ActivityKind(models.TextChoices):
    CALL = "call", "โทรศัพท์"
    LINE = "line", "LINE"
    EMAIL = "email", "อีเมล"
    MEETING = "meeting", "ประชุม/นัดพบ"
    SITE_VISIT = "site_visit", "สำรวจหน้างาน"
    NOTE = "note", "บันทึก"


class Activity(TenantScopedModel):
    """A logged interaction; linked to a lead and/or a deal and/or a customer/contact (all optional).

    Inbound LINE messages land here (kind=LINE) attached to the lead — see apps.integrations.line.
    """

    lead = models.ForeignKey(
        "Lead", on_delete=models.CASCADE, related_name="activities", null=True, blank=True
    )
    deal = models.ForeignKey(
        Deal, on_delete=models.CASCADE, related_name="activities", null=True, blank=True
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="activities", null=True, blank=True
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, related_name="activities", null=True, blank=True
    )
    kind = models.CharField(
        "ประเภท", max_length=20, choices=ActivityKind.choices, default=ActivityKind.NOTE
    )
    body = models.TextField("รายละเอียด", blank=True)
    occurred_at = models.DateTimeField("เกิดขึ้นเมื่อ", default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="crm_activities",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ("-occurred_at",)
        verbose_name = "กิจกรรม"
        verbose_name_plural = "กิจกรรม"

    def __str__(self) -> str:
        return f"{self.get_kind_display()} — {self.occurred_at:%Y-%m-%d}"


class TaskKind(models.TextChoices):
    CALLBACK = "callback", "โทรกลับ"
    SEND_SAMPLE = "send_sample", "ส่งตัวอย่าง/สี"
    SITE_SURVEY = "site_survey", "นัดสำรวจหน้างาน"
    SEND_QUOTE = "send_quote", "ส่งใบเสนอราคา"
    FOLLOW_UP = "follow_up", "ติดตาม"
    OTHER = "other", "อื่น ๆ"


class TaskStatus(models.TextChoices):
    OPEN = "open", "ค้างอยู่"
    DONE = "done", "เสร็จแล้ว"
    CANCELLED = "cancelled", "ยกเลิก"


class Task(TenantScopedModel):
    deal = models.ForeignKey(
        Deal, on_delete=models.CASCADE, related_name="tasks", null=True, blank=True
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="tasks", null=True, blank=True
    )
    kind = models.CharField(
        "ประเภท", max_length=20, choices=TaskKind.choices, default=TaskKind.FOLLOW_UP
    )
    description = models.CharField("รายละเอียด", max_length=500, blank=True)
    due_at = models.DateTimeField("กำหนดเสร็จ", null=True, blank=True)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="crm_tasks",
        null=True,
        blank=True,
    )
    status = models.CharField(
        "สถานะ", max_length=10, choices=TaskStatus.choices, default=TaskStatus.OPEN
    )
    completed_at = models.DateTimeField("เสร็จเมื่อ", null=True, blank=True)

    class Meta:
        ordering = ("due_at", "-created_at")
        verbose_name = "งาน"
        verbose_name_plural = "งาน"
        indexes = [models.Index(fields=["tenant", "assignee", "status"])]

    def __str__(self) -> str:
        return self.description or self.get_kind_display()


# --- Leads --------------------------------------------------------------------
class LeadStatus(models.TextChoices):
    NEW = "new", "ใหม่"
    QUALIFIED = "qualified", "คัดกรองแล้ว"
    CONVERTED = "converted", "แปลงเป็นดีลแล้ว"
    DISQUALIFIED = "disqualified", "ไม่ผ่านคัดกรอง"


class Lead(TenantScopedModel):
    """An inbound enquiry before it becomes a deal. Captured from a web form, LINE, phone, etc."""

    name = models.CharField("ชื่อผู้ติดต่อ", max_length=200)
    company_name = models.CharField("บริษัท/หน่วยงาน", max_length=255, blank=True)
    phone = models.CharField("โทรศัพท์", max_length=50, blank=True)
    email = models.EmailField("อีเมล", blank=True)
    line_id = models.CharField("LINE", max_length=100, blank=True)
    channel = models.CharField(
        "ช่องทาง", max_length=20, choices=LeadChannel.choices, default=LeadChannel.WEB_FORM
    )
    source = models.CharField(
        "แหล่งที่มา", max_length=255, blank=True, help_text="เช่น ชื่อแคมเปญ / ผู้แนะนำ"
    )
    product_interest = models.CharField("สินค้าที่สนใจ", max_length=255, blank=True)
    budget = models.DecimalField(
        "งบประมาณโดยประมาณ", max_digits=18, decimal_places=2, null=True, blank=True
    )
    message = models.TextField("ข้อความ", blank=True)
    status = models.CharField(
        "สถานะ", max_length=20, choices=LeadStatus.choices, default=LeadStatus.NEW
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_leads",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, related_name="leads", null=True, blank=True
    )
    deal = models.ForeignKey(
        Deal, on_delete=models.SET_NULL, related_name="leads", null=True, blank=True
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Lead"
        verbose_name_plural = "Leads"
        indexes = [models.Index(fields=["tenant", "status"])]

    def __str__(self) -> str:
        return f"{self.name}{f' / {self.company_name}' if self.company_name else ''}"


# --- Sales targets (reports — REQUIREMENTS.md §4.9 FR-9.5) --------------------
class SalesTarget(TenantScopedModel):
    """A monthly sales target — per salesperson, or team-wide when ``salesperson`` is null."""

    salesperson = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sales_targets",
        null=True,
        blank=True,
        help_text="เว้นว่าง = เป้าของทั้งทีม",
    )
    year = models.PositiveIntegerField("ปี (ค.ศ.)")
    month = models.PositiveSmallIntegerField("เดือน (1–12)")
    amount = models.DecimalField("เป้ายอดขาย (บาท)", max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ("-year", "-month")
        verbose_name = "เป้ายอดขาย"
        verbose_name_plural = "เป้ายอดขาย"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "salesperson", "year", "month"], name="uniq_sales_target"
            )
        ]

    def __str__(self) -> str:
        sp = self.salesperson
        who = sp.get_full_name() if sp else "ทั้งทีม"
        return f"{self.year}-{self.month:02d} · {who}: {self.amount}"
