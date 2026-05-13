from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import SignupForm
from .models import TwoFactorDevice
from .totp import new_secret, otpauth_uri, verify

_TFA_SESSION_KEY = "_2fa_pending_user_id"


def _user_pk(request: HttpRequest) -> int:
    """Authenticated user's pk as ``int``. Use after a ``@login_required`` guard."""
    return int(request.user.pk)  # type: ignore[arg-type]


class TwoFactorLoginView(LoginView):
    """``django.contrib.auth.views.LoginView`` + a TOTP step for users who have a confirmed device.

    On a valid password, if the user has a confirmed TOTP device we *don't* log them in yet:
    we stash their id in the session and redirect to ``accounts:two_factor_verify``."""

    template_name = "accounts/login.html"

    def form_valid(self, form):
        user = form.get_user()
        device = TwoFactorDevice.objects.filter(user=user, confirmed=True).first()
        if device is None:
            return super().form_valid(form)
        # Hold off on login; remember which user is mid-flight + where they were going.
        self.request.session[_TFA_SESSION_KEY] = user.pk
        self.request.session["_2fa_redirect"] = self.get_success_url()
        return redirect("accounts:two_factor_verify")


@require_http_methods(["GET", "POST"])
def two_factor_verify(request: HttpRequest) -> HttpResponse:
    user_id = request.session.get(_TFA_SESSION_KEY)
    if not user_id:
        return redirect("accounts:login")
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        request.session.pop(_TFA_SESSION_KEY, None)
        return redirect("accounts:login")
    device = TwoFactorDevice.objects.filter(user=user, confirmed=True).first()
    if device is None:  # device was deleted between the two steps
        request.session.pop(_TFA_SESSION_KEY, None)
        login(request, user)
        return redirect("core:home")
    error = ""
    if request.method == "POST":
        code = request.POST.get("code", "")
        if verify(device.secret, code):
            request.session.pop(_TFA_SESSION_KEY, None)
            redirect_to = request.session.pop("_2fa_redirect", "")
            login(request, user)
            return redirect(redirect_to or "core:home")
        error = "รหัสไม่ถูกต้อง โปรดลองอีกครั้ง"
    return render(request, "accounts/two_factor_verify.html", {"error": error})


@login_required
def two_factor_settings(request: HttpRequest) -> HttpResponse:
    """Account-security page: show 2FA status, with an enable-flow + a disable form."""
    device = TwoFactorDevice.objects.filter(user_id=_user_pk(request)).first()
    return render(
        request,
        "accounts/two_factor_settings.html",
        {"device": device},
    )


@login_required
@require_http_methods(["GET", "POST"])
def two_factor_enable(request: HttpRequest) -> HttpResponse:
    """Step 1: generate a (pending) secret + show its otpauth URI; Step 2: confirm with a code."""
    device, _ = TwoFactorDevice.objects.get_or_create(
        user_id=_user_pk(request), defaults={"secret": new_secret(), "confirmed": False}
    )
    if device.confirmed:
        messages.info(request, "2FA เปิดใช้งานอยู่แล้ว")
        return redirect("accounts:two_factor_settings")
    error = ""
    if request.method == "POST":
        code = request.POST.get("code", "")
        if verify(device.secret, code):
            device.confirmed = True
            device.confirmed_at = timezone.now()
            device.save(update_fields=["confirmed", "confirmed_at"])
            messages.success(request, "เปิดใช้งาน 2FA แล้ว")
            return redirect("accounts:two_factor_settings")
        error = "รหัสไม่ถูกต้อง — ลองอีกครั้งจากแอป Authenticator ของคุณ"
    uri = otpauth_uri(device.secret, account_name=str(getattr(request.user, "email", "")))
    return render(
        request,
        "accounts/two_factor_enable.html",
        {"device": device, "otpauth_uri": uri, "error": error},
    )


@login_required
@require_http_methods(["POST"])
def two_factor_disable(request: HttpRequest) -> HttpResponse:
    """Disable 2FA — re-prompt for the user's password to be safe."""
    password = request.POST.get("password", "")
    if not request.user.check_password(password):
        messages.error(request, "รหัสผ่านไม่ถูกต้อง")
        return redirect("accounts:two_factor_settings")
    TwoFactorDevice.objects.filter(user_id=_user_pk(request)).delete()
    messages.success(request, "ปิดใช้งาน 2FA แล้ว")
    return redirect("accounts:two_factor_settings")


def signup(request: HttpRequest) -> HttpResponse:
    """Self-serve signup: create a Tenant + CompanyProfile + owner User + Membership, seed the
    default pipeline, log the new owner in and send them to onboarding."""
    if request.user.is_authenticated:
        return redirect("core:home")
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            from apps.accounts.models import Membership, Role
            from apps.tenants.models import Plan, Tenant

            with transaction.atomic():
                # The post_save signal (apps/crm/signals) provisions a CompanyProfile + the
                # default pipeline for a new Tenant. We just set the company name and the owner.
                tenant = Tenant.objects.create(
                    name=data["workspace_name"], slug=data["slug"], plan=Plan.TRIAL
                )
                profile = tenant.company_profile
                profile.name_th = data["workspace_name"]
                profile.save(update_fields=["name_th"])
                user = get_user_model().objects.create_user(
                    email=data["email"], password=data["password"], full_name=data["full_name"]
                )
                Membership.objects.create(user=user, tenant=tenant, role=Role.OWNER)
            login(request, user)
            return redirect("workspace:onboarding")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})
