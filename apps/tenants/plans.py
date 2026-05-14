"""Plan registry — source of truth for pricing tiers, limits and feature flags.

Pure-Python data; no DB. The `Plan` enum in `apps.tenants.models` stores the code on `Tenant`;
this module maps codes to specs. Per CLAUDE.md §6 (config over customization): every variable
that "varies by customer" lives in a PlanSpec field, not in branches in code.

Reference: salesdee pricing (4 tiers + trial + add-ons). Prices in THB, monthly unless noted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class PlanLimits:
    """Hard caps the plan grants per billing period (calendar month, Asia/Bangkok)."""

    users: int  # active memberships
    line_msgs: int  # inbound LINE messages counted per period
    ai_drafts: int  # AI quote-drafts + reply-drafts + summaries
    tax_invoices: int  # issued TAX_INVOICE per period (hard-blocks at cap)
    storage_gb: int  # uploaded media + PDFs (not enforced yet)
    audit_retention_days: int  # AuditEvent purge horizon (not enforced yet)

    # Sentinels: -1 = unlimited
    @staticmethod
    def unlimited() -> int:
        return -1

    def is_unlimited(self, kind: str) -> bool:
        return getattr(self, kind, 0) == -1

    def cap(self, kind: str) -> int:
        return getattr(self, kind)


@dataclass(frozen=True)
class PlanFeatures:
    """Boolean / categorical feature gates."""

    billing_module: bool = False  # tax invoice / receipt / CN / DN / AR / statements
    white_label_pdf: bool = False  # remove "powered by salesdee." from PDFs
    custom_domain: bool = False  # TenantDomain visible / verifiable
    api_access: str = "none"  # "none" | "read" | "full"
    e_tax_invoice: bool = False  # e-Tax module (Phase 3)
    priority_support: bool = False  # email priority + chat
    sla: bool = False  # 99.5%/mo + phone


@dataclass(frozen=True)
class PlanSpec:
    code: str
    label_th: str
    tagline_th: str
    monthly_thb: Decimal  # 0 for trial / free
    annual_thb: Decimal  # 17% off (≈ 10 months)
    limits: PlanLimits
    features: PlanFeatures
    is_featured: bool = False  # ⭐ highlight on pricing table
    is_public: bool = True  # show on pricing page
    extras_th: list[str] = field(default_factory=list)  # bullets under the tier

    @property
    def annual_monthly_equivalent(self) -> Decimal:
        return (self.annual_thb / 12).quantize(Decimal("1"))


# ─── tiers ──────────────────────────────────────────────────────────────────

PLANS: dict[str, PlanSpec] = {
    "free": PlanSpec(
        code="free",
        label_th="Free",
        tagline_th="ทดลองทุกฟีเจอร์หลัก · ไม่ตัดบัตร · ใช้ได้ตลอด",
        monthly_thb=Decimal("0"),
        annual_thb=Decimal("0"),
        limits=PlanLimits(
            users=1,
            line_msgs=100,
            ai_drafts=10,
            tax_invoices=0,
            storage_gb=1,
            audit_retention_days=14,
        ),
        features=PlanFeatures(
            billing_module=False,
            white_label_pdf=False,
            custom_domain=False,
            api_access="none",
            e_tax_invoice=False,
            priority_support=False,
            sla=False,
        ),
        is_public=True,
        extras_th=[
            "ผู้ใช้ 1 คน · ใบเสนอราคาไม่จำกัด",
            "ไลน์ 100 ข้อความ/เดือน · ผู้ช่วยเอไอ 10 ดราฟต์/เดือน",
            "แสดง 'powered by salesdee.' บนใบเสนอราคา",
            "ไม่รวมระบบบัญชี (อัปเกรดเป็น Pro)",
        ],
    ),
    "starter": PlanSpec(
        code="starter",
        label_th="Starter",
        tagline_th="ทีมเล็ก 1-3 คน · ขยับจาก Excel",
        monthly_thb=Decimal("690"),
        annual_thb=Decimal("6900"),
        limits=PlanLimits(
            users=2,
            line_msgs=500,
            ai_drafts=30,
            tax_invoices=0,
            storage_gb=5,
            audit_retention_days=30,
        ),
        features=PlanFeatures(api_access="none"),
        extras_th=[
            "ไลน์ OA 1 บัญชี",
            "ใบเสนอราคาไม่จำกัด",
            "ใบกำกับภาษี · ใบเสร็จ — ยังไม่รวม (อัปเกรดเป็น Growth)",
            "ลบ 'powered by salesdee.' ได้",
        ],
    ),
    "growth": PlanSpec(
        code="growth",
        label_th="Growth",
        tagline_th="ทีมขาย 3-5 คน · ปิดดีลเร็วผ่านไลน์",
        monthly_thb=Decimal("1890"),
        annual_thb=Decimal("18900"),
        limits=PlanLimits(
            users=5,
            line_msgs=3000,
            ai_drafts=200,
            tax_invoices=0,
            storage_gb=20,
            audit_retention_days=90,
        ),
        features=PlanFeatures(white_label_pdf=True, api_access="none"),
        is_featured=True,
        extras_th=[
            "ไลน์ OA 1 บัญชี · 3,000 ข้อความ/เดือน",
            "ผู้ช่วยเอไอเต็มที่ · 200 ดราฟต์/เดือน",
            "ใบเสนอราคาไม่จำกัด · ส่งกลับเข้าไลน์อัตโนมัติ",
            "ทีม 5 คน · ลบ 'powered by salesdee.' บนใบเสนอราคา",
            "ระบบบัญชี (ใบกำกับภาษี · ใบเสร็จ · ลูกหนี้) — ยังไม่รวม (อัปเกรดเป็น Pro)",
            "บันทึกตรวจสอบ 90 วัน",
        ],
    ),
    "pro": PlanSpec(
        code="pro",
        label_th="Pro",
        tagline_th="บริษัทกลาง 5-12 คน · ใบกำกับภาษี + ลูกหนี้ครบ",
        monthly_thb=Decimal("3890"),
        annual_thb=Decimal("38900"),
        limits=PlanLimits(
            users=12,
            line_msgs=10000,
            ai_drafts=800,
            tax_invoices=500,
            storage_gb=100,
            audit_retention_days=365,
        ),
        features=PlanFeatures(
            billing_module=True,
            white_label_pdf=True,
            custom_domain=True,
            api_access="read",
            priority_support=True,
        ),
        extras_th=[
            "ทุกอย่างใน Growth + ระบบบัญชีเต็มชุด:",
            "ใบกำกับภาษีเต็มรูป (ม.86/4) · 500 ใบ/เดือน",
            "ใบเสร็จ · ใบลดหนี้ · ใบเพิ่มหนี้ · ใบแจ้งยอด",
            "ลูกหนี้คงค้าง · รายงานภาษีขาย (ภ.พ.30)",
            "ไลน์ OA สูงสุด 3 บัญชี · 10,000 ข้อความ/เดือน",
            "ผู้ช่วยเอไอ · 800 ดราฟต์/เดือน",
            "โดเมนของตัวเอง (crm.บริษัทคุณ.com)",
            "API อ่านข้อมูล + webhook",
            "บันทึกตรวจสอบ 1 ปี",
            "ซัพพอร์ตอีเมลด่วน + แชต",
        ],
    ),
    "business": PlanSpec(
        code="business",
        label_th="Business",
        tagline_th="บริษัทใหญ่ · หลายสาขา · มาตรฐานเอกสาร 5 ปี",
        monthly_thb=Decimal("9900"),
        annual_thb=Decimal("99000"),
        limits=PlanLimits(
            users=PlanLimits.unlimited(),
            line_msgs=PlanLimits.unlimited(),
            ai_drafts=PlanLimits.unlimited(),
            tax_invoices=PlanLimits.unlimited(),
            storage_gb=500,
            audit_retention_days=1825,  # 5 ปี (PDPA + Revenue Code)
        ),
        features=PlanFeatures(
            billing_module=True,
            white_label_pdf=True,
            custom_domain=True,
            api_access="full",
            e_tax_invoice=True,
            priority_support=True,
            sla=True,
        ),
        extras_th=[
            "ผู้ใช้ไม่จำกัด · ไลน์ OA ไม่จำกัด",
            "ผู้ช่วยเอไอไม่จำกัด (fair use)",
            "ใบกำกับภาษี ไม่จำกัด · ใบกำกับอิเล็กทรอนิกส์",
            "API เต็ม (อ่าน + เขียน + webhook)",
            "เอกสารแบบไม่มีตราของเรา (white-label)",
            "บันทึกตรวจสอบ 5 ปี (ตามกฎหมาย)",
            "SLA 99.5% · ซัพพอร์ตทางโทรศัพท์ · พาเริ่มใช้งานแบบ 1 ต่อ 1",
        ],
    ),
}


PUBLIC_TIER_ORDER: tuple[str, ...] = ("free", "starter", "growth", "pro", "business")


def get(code: str) -> PlanSpec:
    """Return the spec for a plan code, falling back to free for unknown codes."""
    return PLANS.get(code, PLANS["free"])


def public_tiers() -> list[PlanSpec]:
    """Tiers shown on pricing pages."""
    return [PLANS[code] for code in PUBLIC_TIER_ORDER]


# ─── usage kinds (used by quota.py in Phase B) ──────────────────────────────

USAGE_KINDS: tuple[str, ...] = ("line_msgs", "ai_drafts", "tax_invoices")

USAGE_LABELS_TH: dict[str, str] = {
    "line_msgs": "ข้อความไลน์",
    "ai_drafts": "ผู้ช่วยเอไอ",
    "tax_invoices": "ใบกำกับภาษี",
}
