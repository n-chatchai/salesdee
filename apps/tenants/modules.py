"""Module status registry — what's on/off for the current tenant, and why.

Read-only view (Phase A of feature switches). Each ``ModuleStatus`` collects:
- the module's user-facing label
- its category (core / plan-gated / config / per-user / future)
- whether it's currently enabled for ``request.tenant``
- a one-line "why" note + an optional "how to turn it on" link

A future Phase B can add toggles for the categories where toggling makes sense
(per-tenant LINE/AI keys, beta flags). Plan-gated modules will always require
an upgrade.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from django.conf import settings
from django.http import HttpRequest
from django.urls import reverse

from . import plans as plan_registry

Category = Literal["core", "plan", "config", "per-user", "future"]


@dataclass(frozen=True)
class ModuleStatus:
    code: str
    label_th: str
    category: Category
    enabled: bool
    note_th: str
    fix_th: str = ""
    fix_url: str | None = None
    overridden: bool = False  # True if a TenantFeatureOverride is overriding the plan default
    override_reason: str = ""
    platform_disabled: bool = False  # True if PLATFORM_DISABLED_MODULES kill-switches this code


def _line_configured(tenant) -> bool:
    from apps.integrations.models import LineIntegration

    line = LineIntegration.objects.filter(tenant=tenant).first()
    return bool(line and line.is_active and line.channel_access_token)


def _ai_configured() -> bool:
    return bool(getattr(settings, "ANTHROPIC_API_KEY", ""))


def _users_active(tenant) -> int:
    from apps.accounts.models import Membership

    return Membership.objects.filter(tenant=tenant, is_active=True).count()


def get_modules(request: HttpRequest) -> list[ModuleStatus]:
    """All modules + current status for ``request.tenant``. Tenant must be set
    (middleware guarantees this for in-app views)."""
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        return []
    from .features import feature_enabled, get_override, is_platform_disabled

    plan = plan_registry.get(tenant.plan)
    L = plan.limits

    line_ok = _line_configured(tenant)
    ai_ok = _ai_configured()
    members = _users_active(tenant)

    def _plan(code: str) -> tuple[bool, bool, str, bool]:
        """Return (enabled, overridden, override_reason, platform_disabled) for a plan-gated module."""
        platform_off = is_platform_disabled(code)
        enabled = feature_enabled(tenant, code)
        ov = get_override(tenant, code)
        return enabled, bool(ov), (ov.reason if ov else ""), platform_off

    # cap_note: e.g. "200 ดราฟต์/เดือน" / "ไม่จำกัด"
    def cap(kind: str, unit_th: str) -> str:
        v = L.cap(kind)
        return "ไม่จำกัด" if v == -1 else f"{v:,} {unit_th}"

    user_cap = "ไม่จำกัด" if L.users == -1 else f"{members}/{L.users} คน"

    line_url = reverse("workspace:settings_line")
    billing_settings_url = reverse("workspace:settings_billing")

    return [
        # ── core (always on) ────────────────────────────────────────────────
        ModuleStatus(
            code="crm",
            label_th="ลูกค้าและดีล (CRM)",
            category="core",
            enabled=True,
            note_th=f"ผู้ใช้ {user_cap}",
        ),
        ModuleStatus(
            code="crm_legacy",
            label_th="CRM เก่า · kanban / leads / tasks / deal-detail / AI reply",
            category="config",
            enabled=not is_platform_disabled("crm_legacy"),
            platform_disabled=is_platform_disabled("crm_legacy"),
            note_th=(
                "ปิดอยู่ — ไม่อยู่ใน design ใหม่ (เก็บโค้ดไว้เผื่อเปิดกลับ)"
                if is_platform_disabled("crm_legacy")
                else "เปิดอยู่ (PLATFORM_DISABLED_MODULES ไม่มี 'crm_legacy')"
            ),
            fix_th="ลบ 'crm_legacy' ออกจาก PLATFORM_DISABLED_MODULES ใน .env เพื่อเปิดกลับ",
        ),
        ModuleStatus(
            code="catalog",
            label_th="แคตตาล็อกสินค้า",
            category="core",
            enabled=True,
            note_th="หมวด · variant · บันเดิล · ออปชัน",
        ),
        ModuleStatus(
            code="quotes",
            label_th="ใบเสนอราคา",
            category="core",
            enabled=True,
            note_th="ใบเสนอราคาไม่จำกัด · จัดกลุ่มห้อง · revision",
        ),
        ModuleStatus(
            code="audit",
            label_th="บันทึกตรวจสอบ",
            category="core",
            enabled=True,
            note_th=f"เก็บ {L.audit_retention_days} วัน",
        ),
        # ── config (per-tenant or env-level) ────────────────────────────────
        ModuleStatus(
            code="line",
            label_th="ไลน์ OA",
            category="config",
            enabled=line_ok,
            note_th=(f"เชื่อมแล้ว · {cap('line_msgs', 'ข้อความ/เดือน')}" if line_ok else "ยังไม่ได้เชื่อม"),
            fix_th="ใส่ Channel Secret + Access Token",
            fix_url=line_url,
        ),
        ModuleStatus(
            code="ai",
            label_th="ผู้ช่วยเอไอ",
            category="config",
            enabled=ai_ok,
            note_th=(
                f"เปิด · {cap('ai_drafts', 'ดราฟต์/เดือน')}"
                if ai_ok
                else "ยังไม่ได้ตั้ง ANTHROPIC_API_KEY ใน .env"
            ),
            fix_th="ใส่ ANTHROPIC_API_KEY ใน .env แล้วรีสตาร์ทเซิร์ฟเวอร์",
        ),
        # ── plan-gated (subject to TenantFeatureOverride) ───────────────────
        *(
            (
                _plan_module(
                    "billing",
                    "ระบบบัญชี (ใบกำกับภาษี · ใบเสร็จ · ลูกหนี้)",
                    on_note=f"เปิด · ออกได้ {cap('tax_invoices', 'ใบ/เดือน')}",
                    off_note="แพ็กเกจนี้ยังไม่รวม — อัปเกรดเป็น Pro หรือสูงกว่า",
                    off_fix="อัปเกรดแพ็กเกจ",
                    upgrade_url=billing_settings_url,
                    _plan=_plan,
                ),
                _plan_module(
                    "e_tax",
                    "ใบกำกับภาษีอิเล็กทรอนิกส์ (e-Tax)",
                    on_note="เปิด",
                    off_note="เฉพาะแพ็กเกจ Business",
                    off_fix="อัปเกรดเป็น Business",
                    upgrade_url=billing_settings_url,
                    _plan=_plan,
                ),
                _plan_module(
                    "white_label",
                    "เอกสารแบบไม่มีตราของเรา (white-label)",
                    on_note="เปิด · ไม่แสดง 'powered by salesdee.'",
                    off_note="แสดง 'powered by salesdee.' บนใบเสนอราคา",
                    off_fix="อัปเกรดเป็น Growth หรือสูงกว่า",
                    upgrade_url=billing_settings_url,
                    _plan=_plan,
                ),
                _plan_module(
                    "custom_domain",
                    "โดเมนของตัวเอง",
                    on_note="เปิด · ตั้งค่าโดเมนที่ /admin/tenants/tenantdomain/",
                    off_note="ใช้ได้แค่ subdomain ในตัว · อัปเกรดเป็น Pro",
                    off_fix="อัปเกรดเป็น Pro",
                    upgrade_url=billing_settings_url,
                    _plan=_plan,
                ),
                _plan_module(
                    "api",
                    "API + webhook",
                    on_note=(
                        "อ่าน + เขียน + webhook"
                        if plan.features.api_access == "full"
                        else "อ่านอย่างเดียว + webhook"
                    ),
                    off_note="ยังไม่เปิด",
                    off_fix="อัปเกรดเป็น Pro หรือ Business",
                    upgrade_url=billing_settings_url,
                    _plan=_plan,
                ),
                _plan_module(
                    "priority_support",
                    "ซัพพอร์ตด่วน",
                    on_note="เปิด · อีเมล priority + แชต",
                    off_note="ซัพพอร์ตอีเมลตามคิวปกติ",
                    _plan=_plan,
                ),
                _plan_module(
                    "sla",
                    "SLA 99.5%",
                    on_note="เปิด · ซัพพอร์ตทางโทรศัพท์",
                    off_note="ไม่มี SLA — เฉพาะ Business",
                    _plan=_plan,
                ),
            )
        ),
        # ── per-user opt-in ─────────────────────────────────────────────────
        ModuleStatus(
            code="2fa",
            label_th="ยืนยันตัวตน 2 ขั้น (2FA)",
            category="per-user",
            enabled=_user_has_2fa(request),
            note_th=("เปิดสำหรับบัญชีคุณแล้ว" if _user_has_2fa(request) else "ผู้ใช้แต่ละคนเปิดเอง"),
            fix_th="เปิดในหน้าความปลอดภัย",
            fix_url=_safe_url("accounts:two_factor_settings"),
        ),
        # ── future (not built) ──────────────────────────────────────────────
        ModuleStatus(
            code="fulfillment",
            label_th="ออร์เดอร์ · ผลิต · ส่ง · ติดตั้ง · รับประกัน",
            category="future",
            enabled=False,
            note_th="Phase 2 — ยังไม่พัฒนา",
        ),
        ModuleStatus(
            code="accounting",
            label_th="บัญชีแยกประเภท · สมุดรายวัน · งบ",
            category="future",
            enabled=False,
            note_th="Phase 3 — ยังไม่พัฒนา",
        ),
        # ── platform infra (read-only signals) ──────────────────────────────
        ModuleStatus(
            code="rls",
            label_th="Row-Level Security (Postgres)",
            category="config",
            enabled=getattr(settings, "RLS_ENABLED", False),
            note_th=(
                "เปิดอยู่ — แยกข้อมูล tenant ที่ระดับ DB"
                if getattr(settings, "RLS_ENABLED", False)
                else "ปิด (ใช้ใน dev) — TenantManager ทำหน้าที่แยกข้อมูลแทน"
            ),
            fix_th="ตั้ง RLS_ENABLED=true ใน .env (prod)",
        ),
        ModuleStatus(
            code="r2_storage",
            label_th="ที่เก็บไฟล์ Cloudflare R2",
            category="config",
            enabled=getattr(settings, "USE_R2", False),
            note_th=(
                "เปิดอยู่ — รูป/PDF เก็บบน R2"
                if getattr(settings, "USE_R2", False)
                else "ใช้ไฟล์ระบบในเครื่อง (เหมาะกับ dev เท่านั้น)"
            ),
            fix_th="ตั้ง USE_R2=true + R2_* env vars (prod)",
        ),
    ]


def _user_has_2fa(request: HttpRequest) -> bool:
    from apps.accounts.models import TwoFactorDevice

    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return TwoFactorDevice.objects.filter(user=user, confirmed=True).exists()


def _safe_url(name: str) -> str | None:
    try:
        return reverse(name)
    except Exception:  # pragma: no cover
        return None


def _plan_module(
    code: str,
    label_th: str,
    *,
    on_note: str,
    off_note: str,
    off_fix: str = "",
    upgrade_url: str | None = None,
    _plan,
) -> ModuleStatus:
    """Build a plan-gated ModuleStatus honouring overrides + platform kill switch."""
    enabled, overridden, reason, platform_off = _plan(code)
    if platform_off:
        note = "ปิดทั้งระบบโดยผู้ดูแลแพลตฟอร์ม (incident / maintenance)"
        fix = ""
        url = None
    elif enabled:
        note = on_note
        fix = ""
        url = None
    else:
        note = off_note
        fix = off_fix
        url = upgrade_url
    return ModuleStatus(
        code=code,
        label_th=label_th,
        category="plan",
        enabled=enabled,
        note_th=note,
        fix_th=fix,
        fix_url=url,
        overridden=overridden and not platform_off,
        override_reason=reason if not platform_off else "",
        platform_disabled=platform_off,
    )


CATEGORY_LABELS_TH: dict[str, str] = {
    "core": "หลัก (เปิดตลอด)",
    "config": "ตั้งค่าได้",
    "plan": "ตามแพ็กเกจ",
    "per-user": "ตามผู้ใช้",
    "future": "ยังไม่พัฒนา",
}
