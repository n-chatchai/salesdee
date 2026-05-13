from __future__ import annotations

from django.contrib.auth import get_user_model, login
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .forms import SignupForm


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
