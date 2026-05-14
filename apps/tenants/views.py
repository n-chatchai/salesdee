"""In-app workspace settings, first-run setup wizard, and system-status page (CLAUDE.md M4)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.models import Membership, Role
from apps.core.permissions import membership_of
from apps.crm.models import PipelineStage
from apps.integrations.models import LineIntegration

from . import plans as plan_registry
from .forms import (
    CompanyProfileForm,
    DocumentNumberSequenceForm,
    LineIntegrationForm,
    MemberInviteForm,
    MemberRoleForm,
    PipelineStageForm,
)
from .models import BillingCycle, CompanyProfile

User = get_user_model()


def _tenant(request: HttpRequest):
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        raise Http404("ไม่พบ workspace")
    return tenant


def _can_admin(request: HttpRequest) -> bool:
    """Owners and managers may edit workspace settings; sales/viewer may not."""
    m = membership_of(request)
    return m is not None and m.role in (Role.OWNER, Role.MANAGER)


def _company(request: HttpRequest, *, create: bool = False) -> CompanyProfile | None:
    tenant = _tenant(request)
    cp = CompanyProfile.objects.filter(tenant=tenant).first()
    if cp is None and create:
        cp = CompanyProfile(tenant=tenant, name_th=tenant.name)
    return cp


def onboarding_status(request: HttpRequest) -> dict:
    """Derive setup-wizard progress from existing data — no model. Returns step flags + remaining."""
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        return {"steps": [], "done": True, "remaining": 0, "complete": True}
    from apps.catalog.models import Product

    cp = CompanyProfile.objects.filter(tenant=tenant).first()
    line = LineIntegration.objects.filter(tenant=tenant).first()
    steps = [
        {"n": 1, "key": "company", "label": "ข้อมูลบริษัท", "done": bool(cp and cp.name_th)},
        {"n": 2, "key": "brand", "label": "โลโก้และแบรนด์", "done": bool(cp and cp.logo)},
        {"n": 3, "key": "product", "label": "สินค้าชิ้นแรก", "done": Product.objects.exists()},
        {
            "n": 4,
            "key": "team",
            "label": "ทีมงานและสิทธิ์",
            "done": Membership.objects.filter(tenant=tenant, is_active=True).count() > 1,
        },
        {
            "n": 5,
            "key": "line",
            "label": "เชื่อม LINE OA",
            "done": bool(line and (line.channel_id or line.channel_access_token)),
        },
    ]
    remaining = sum(1 for s in steps if not s["done"])
    return {"steps": steps, "remaining": remaining, "complete": remaining == 0}


# --------------------------------------------------------------------------- hub / status


@login_required
def settings_hub(request: HttpRequest) -> HttpResponse:
    tenant = _tenant(request)
    ctx = {
        "tenant": tenant,
        "company": CompanyProfile.objects.filter(tenant=tenant).first(),
        "line": LineIntegration.objects.filter(tenant=tenant).first(),
        "stage_count": PipelineStage.objects.count(),
        "member_count": Membership.objects.filter(tenant=tenant, is_active=True).count(),
        "can_admin": _can_admin(request),
        "onboarding": onboarding_status(request),
    }
    return render(request, "tenants/settings_hub.html", ctx)


@login_required
def system_status(request: HttpRequest) -> HttpResponse:
    from django.conf import settings as dj_settings
    from django.db import connection

    from apps.integrations.ai import ai_is_configured

    tenant = _tenant(request)
    line = LineIntegration.objects.filter(tenant=tenant).first()
    db_ok = True
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
            c.fetchone()
    except Exception:  # pragma: no cover - defensive
        db_ok = False
    checks = [
        {
            "label": "ฐานข้อมูล",
            "ok": db_ok,
            "note": "เชื่อมต่อ PostgreSQL ได้" if db_ok else "เชื่อมต่อไม่ได้",
        },
        {
            "label": "LINE OA",
            "ok": bool(line and line.is_active and line.channel_access_token),
            "note": "เชื่อมแล้ว" if (line and line.channel_access_token) else "ยังไม่ได้เชื่อม",
            "warn": not (line and line.channel_access_token),
        },
        {
            "label": "ผู้ช่วย AI",
            "ok": ai_is_configured(),
            "note": "พร้อมใช้งาน" if ai_is_configured() else "ยังไม่ได้ตั้งค่า ANTHROPIC_API_KEY",
            "warn": not ai_is_configured(),
        },
        {
            "label": "งานเบื้องหลัง (worker)",
            "ok": True,
            "warn": True,
            "note": "ต้องรัน `manage.py db_worker` แยกต่างหากเพื่อส่ง PDF/อีเมล/LINE",
        },
        {
            "label": "Row-Level Security",
            "ok": getattr(dj_settings, "RLS_ENABLED", False),
            "warn": not getattr(dj_settings, "RLS_ENABLED", False),
            "note": "เปิดอยู่"
            if getattr(dj_settings, "RLS_ENABLED", False)
            else "ปิด (dev) — ใช้ TenantManager แทน",
        },
    ]
    return render(
        request,
        "tenants/system_status.html",
        {
            "checks": checks,
            "app_version": getattr(dj_settings, "APP_VERSION", "0.1.0"),
            "tenant": tenant,
        },
    )


# --------------------------------------------------------------------------- company


@login_required
def settings_company(request: HttpRequest) -> HttpResponse:
    if not _can_admin(request):
        return HttpResponseForbidden("ต้องเป็นเจ้าของหรือผู้จัดการ")
    instance = _company(request, create=True)
    if request.method == "POST":
        form = CompanyProfileForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "บันทึกข้อมูลบริษัทแล้ว")
            return redirect("workspace:settings_company")
    else:
        form = CompanyProfileForm(instance=instance)
    return render(request, "tenants/settings_company.html", {"form": form})


# --------------------------------------------------------------------------- LINE


@login_required
def settings_line(request: HttpRequest) -> HttpResponse:
    if not _can_admin(request):
        return HttpResponseForbidden("ต้องเป็นเจ้าของหรือผู้จัดการ")
    tenant = _tenant(request)
    instance = LineIntegration.objects.filter(tenant=tenant).first()
    if request.method == "POST":
        form = LineIntegrationForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()
            messages.success(request, "บันทึกการเชื่อม LINE แล้ว")
            return redirect("workspace:settings_line")
    else:
        form = LineIntegrationForm(instance=instance)
    webhook_url = request.build_absolute_uri(
        reverse("integrations:line_webhook", args=[tenant.slug])
    )
    return render(
        request,
        "tenants/settings_line.html",
        {"form": form, "webhook_url": webhook_url, "line": instance},
    )


# --------------------------------------------------------------------------- pipeline


@login_required
def settings_pipeline(request: HttpRequest) -> HttpResponse:
    if not _can_admin(request):
        return HttpResponseForbidden("ต้องเป็นเจ้าของหรือผู้จัดการ")
    if request.method == "POST" and request.POST.get("_action") == "add":
        form = PipelineStageForm(request.POST)
        if form.is_valid():
            stage = form.save(commit=False)
            stage.order = (
                PipelineStage.objects.order_by("-order").values_list("order", flat=True).first()
                or 0
            ) + 1
            stage.save()
            messages.success(request, "เพิ่มขั้นแล้ว")
        return redirect("workspace:settings_pipeline")
    from apps.crm.models import StageKind

    stages = list(PipelineStage.objects.order_by("order", "id"))
    return render(
        request,
        "tenants/settings_pipeline.html",
        {"stages": stages, "add_form": PipelineStageForm(), "kind_choices": StageKind.choices},
    )


@login_required
@require_POST
def pipeline_stage_edit(request: HttpRequest, pk: int) -> HttpResponse:
    if not _can_admin(request):
        return HttpResponseForbidden()
    stage = get_object_or_404(PipelineStage, pk=pk)
    form = PipelineStageForm(request.POST, instance=stage)
    if form.is_valid():
        form.save()
        messages.success(request, "บันทึกแล้ว")
    return redirect("workspace:settings_pipeline")


@login_required
@require_POST
def pipeline_reorder(request: HttpRequest) -> HttpResponse:
    if not _can_admin(request):
        return HttpResponseForbidden()
    ids = request.POST.getlist("order[]") or request.POST.getlist("order")
    for idx, sid in enumerate(ids):
        PipelineStage.objects.filter(pk=sid).update(order=idx)
    return JsonResponse({"ok": True})


# --------------------------------------------------------------------------- numbering


@login_required
def settings_numbering(request: HttpRequest) -> HttpResponse:
    if not _can_admin(request):
        return HttpResponseForbidden("ต้องเป็นเจ้าของหรือผู้จัดการ")
    from apps.quotes.models import DocumentNumberSequence

    if request.method == "POST":
        pk = request.POST.get("pk")
        instance = DocumentNumberSequence.objects.filter(pk=pk).first() if pk else None
        form = DocumentNumberSequenceForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = _tenant(request)
            obj.save()
            messages.success(request, "บันทึกลำดับเลขที่เอกสารแล้ว")
        else:
            messages.error(request, "บันทึกไม่สำเร็จ")
        return redirect("workspace:settings_numbering")
    sequences = list(DocumentNumberSequence.objects.order_by("doc_type", "-year"))
    return render(
        request,
        "tenants/settings_numbering.html",
        {"sequences": sequences, "add_form": DocumentNumberSequenceForm()},
    )


# --------------------------------------------------------------------------- members


@login_required
def settings_members(request: HttpRequest) -> HttpResponse:
    tenant = _tenant(request)
    can_admin = _can_admin(request)
    if request.method == "POST":
        if not can_admin:
            return HttpResponseForbidden("ต้องเป็นเจ้าของหรือผู้จัดการ")
        form = MemberInviteForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].lower().strip()
            # Plan user-cap (Phase B). Only counts NEW members — re-activating an existing
            # membership of the same workspace stays under cap.
            user_limit = plan_registry.get(tenant.plan).limits.cap("users")
            active_count = Membership.objects.filter(tenant=tenant, is_active=True).count()
            already_member = Membership.objects.filter(tenant=tenant, user__email=email).exists()
            if user_limit != -1 and not already_member and active_count >= user_limit:
                messages.error(
                    request,
                    f"แพ็กเกจปัจจุบันรองรับ {user_limit} ผู้ใช้ "
                    f"({active_count}/{user_limit}) — อัปเกรดเพื่อเพิ่มสมาชิก",
                )
                return redirect("workspace:settings_members")
            user, created = User.objects.get_or_create(
                email=email, defaults={"full_name": form.cleaned_data.get("full_name", "")}
            )
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
            membership, m_created = Membership.objects.get_or_create(
                user=user,
                tenant=tenant,
                defaults={
                    "role": form.cleaned_data["role"],
                    "can_see_all_records": form.cleaned_data["can_see_all_records"],
                },
            )
            if not m_created:
                membership.is_active = True
                membership.role = form.cleaned_data["role"]
                membership.can_see_all_records = form.cleaned_data["can_see_all_records"]
                membership.save()
            send_mail(
                "เชิญเข้าใช้งาน salesdee",
                f"คุณได้รับเชิญเข้าร่วม workspace {tenant.name} บน salesdee — เข้าสู่ระบบที่ "
                + request.build_absolute_uri(reverse("accounts:login")),
                None,
                [email],
                fail_silently=True,
            )
            messages.success(request, f"เพิ่มสมาชิก {email} แล้ว และส่งคำเชิญทางอีเมล")
            return redirect("workspace:settings_members")
    else:
        form = MemberInviteForm()
    memberships = list(
        Membership.objects.filter(tenant=tenant)
        .select_related("user")
        .order_by("-is_active", "user__email")
    )
    my_membership = membership_of(request)
    return render(
        request,
        "tenants/settings_members.html",
        {
            "memberships": memberships,
            "form": form,
            "can_admin": can_admin,
            "my_membership": my_membership,
            "role_form": MemberRoleForm(),
        },
    )


@login_required
@require_POST
def member_edit(request: HttpRequest, pk: int) -> HttpResponse:
    if not _can_admin(request):
        return HttpResponseForbidden()
    tenant = _tenant(request)
    m = get_object_or_404(Membership, pk=pk, tenant=tenant)
    if m.user_id == request.user.pk:
        messages.error(request, "เปลี่ยนบทบาทของตัวเองไม่ได้")
        return redirect("workspace:settings_members")
    new_role = request.POST.get("role")
    deactivate = request.POST.get("is_active") in (None, "", "0", "false")
    # Don't strip away the last active owner.
    owners = Membership.objects.filter(tenant=tenant, is_active=True, role=Role.OWNER)
    if m.role == Role.OWNER and (new_role != Role.OWNER or deactivate) and owners.count() <= 1:
        messages.error(request, "ต้องมีเจ้าของอย่างน้อยหนึ่งคน")
        return redirect("workspace:settings_members")
    before = {"role": m.role, "is_active": m.is_active}
    form = MemberRoleForm(request.POST, instance=m)
    if form.is_valid():
        form.save()
        messages.success(request, "บันทึกสมาชิกแล้ว")
        from apps.audit.services import record as audit_record

        audit_record(
            request.user,
            action="membership.role_changed",
            obj=m,
            object_repr=m.user.email,
            changes={"before": before, "after": {"role": m.role, "is_active": m.is_active}},
            ip=request.META.get("REMOTE_ADDR"),
        )
    return redirect("workspace:settings_members")


# --------------------------------------------------------------------------- billing


@login_required
def settings_billing(request: HttpRequest) -> HttpResponse:
    from .quota import caps_for_tenant

    tenant = _tenant(request)
    current = plan_registry.get(tenant.plan)
    ctx = {
        "tenant": tenant,
        "current_plan": current,
        "tiers": plan_registry.public_tiers(),
        "cycles": BillingCycle,
        "can_admin": _can_admin(request),
        "usage": caps_for_tenant(tenant),
    }
    return render(request, "tenants/settings_billing.html", ctx)


@login_required
@require_POST
def plan_change(request: HttpRequest) -> HttpResponse:
    """Owner/manager picks a plan tier and billing cycle. No payment integration yet — this
    just updates the tenant record and writes an audit event. Stripe wiring is Phase D."""
    if not _can_admin(request):
        return HttpResponseForbidden("ต้องเป็นเจ้าของหรือผู้จัดการเท่านั้น")
    tenant = _tenant(request)
    new_code = request.POST.get("plan", "").strip()
    new_cycle = request.POST.get("cycle", BillingCycle.MONTHLY).strip()
    if new_code not in plan_registry.PLANS or new_code == "trial":
        messages.error(request, "เลือกแพ็กเกจไม่ถูกต้อง")
        return redirect("workspace:settings_billing")
    if new_cycle not in BillingCycle.values:
        new_cycle = BillingCycle.MONTHLY
    before = {"plan": tenant.plan, "cycle": tenant.billing_cycle}
    tenant.plan = new_code
    tenant.billing_cycle = new_cycle
    tenant.save(update_fields=["plan", "billing_cycle", "updated_at"])
    messages.success(request, f"เปลี่ยนแพ็กเกจเป็น {plan_registry.get(new_code).label_th} แล้ว")
    from apps.audit.services import record as audit_record

    audit_record(
        request.user,
        action="tenant.plan_changed",
        obj=tenant,
        object_repr=tenant.name,
        changes={"before": before, "after": {"plan": new_code, "cycle": new_cycle}},
        ip=request.META.get("REMOTE_ADDR"),
        tenant=tenant,
    )
    return redirect("workspace:settings_billing")


# --------------------------------------------------------------------------- onboarding wizard


@login_required
def onboarding(request: HttpRequest) -> HttpResponse:
    from apps.catalog.forms import ProductForm

    tenant = _tenant(request)
    status = onboarding_status(request)
    try:
        step = int(request.GET.get("step", "1"))
    except ValueError:
        step = 1
    step = max(1, min(5, step))
    can_admin = _can_admin(request)

    form: object | None = None
    template_step = f"tenants/onboarding/step{step}.html"

    if step == 1:
        instance = _company(request, create=True)
        if request.method == "POST":
            form = CompanyProfileForm(request.POST, request.FILES, instance=instance)
            if isinstance(form, CompanyProfileForm) and form.is_valid():
                form.save()
                return redirect(reverse("workspace:onboarding") + "?step=2")
        else:
            form = CompanyProfileForm(instance=instance)
    elif step == 2:
        instance = _company(request, create=True)
        if request.method == "POST":
            form = CompanyProfileForm(request.POST, request.FILES, instance=instance)
            if isinstance(form, CompanyProfileForm) and form.is_valid():
                form.save()
                return redirect(reverse("workspace:onboarding") + "?step=3")
        else:
            form = CompanyProfileForm(instance=instance)
    elif step == 3:
        if request.method == "POST":
            form = ProductForm(request.POST, request.FILES)
            if isinstance(form, ProductForm) and form.is_valid():
                form.save()
                return redirect(reverse("workspace:onboarding") + "?step=4")
        else:
            form = ProductForm()
    elif step == 4:
        if request.method == "POST":
            if request.POST.get("_skip"):
                return redirect(reverse("workspace:onboarding") + "?step=5")
            form = MemberInviteForm(request.POST)
            if isinstance(form, MemberInviteForm) and form.is_valid() and can_admin:
                email = form.cleaned_data["email"].lower().strip()
                user, created = User.objects.get_or_create(
                    email=email, defaults={"full_name": form.cleaned_data.get("full_name", "")}
                )
                if created:
                    user.set_unusable_password()
                    user.save(update_fields=["password"])
                Membership.objects.get_or_create(
                    user=user,
                    tenant=tenant,
                    defaults={
                        "role": form.cleaned_data["role"],
                        "can_see_all_records": form.cleaned_data["can_see_all_records"],
                    },
                )
                send_mail(
                    "เชิญเข้าใช้งาน salesdee",
                    f"คุณได้รับเชิญเข้าร่วม {tenant.name}",
                    None,
                    [email],
                    fail_silently=True,
                )
                return redirect(reverse("workspace:onboarding") + "?step=4")
        else:
            form = MemberInviteForm()
    elif step == 5:
        line_instance = LineIntegration.objects.filter(tenant=tenant).first()
        if request.method == "POST":
            if request.POST.get("_finish"):
                messages.success(request, "ตั้งค่า workspace เรียบร้อย — เริ่มใช้งานได้เลย")
                return redirect("core:home")
            form = LineIntegrationForm(request.POST, instance=line_instance)
            if isinstance(form, LineIntegrationForm) and form.is_valid():
                obj = form.save(commit=False)
                obj.tenant = tenant
                obj.save()
                messages.success(request, "ตั้งค่า workspace เรียบร้อย — เริ่มใช้งานได้เลย")
                return redirect("core:home")
        else:
            form = LineIntegrationForm(instance=line_instance)

    members = (
        list(Membership.objects.filter(tenant=tenant).select_related("user")) if step == 4 else []
    )
    webhook_url = (
        request.build_absolute_uri(reverse("integrations:line_webhook", args=[tenant.slug]))
        if step == 5
        else ""
    )
    return render(
        request,
        "tenants/onboarding.html",
        {
            "step": step,
            "status": status,
            "form": form,
            "step_template": template_step,
            "tenant": tenant,
            "can_admin": can_admin,
            "members": members,
            "webhook_url": webhook_url,
        },
    )
