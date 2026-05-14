"""Workspace settings, onboarding wizard and public-home tests (M4)."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.models import Membership, Role


@pytest.fixture
def owner(db, tenant):
    from django.contrib.auth import get_user_model

    u = get_user_model().objects.create_user(email="owner@wandeedee.test", password="pw-123456789")
    Membership.objects.create(user=u, tenant=tenant, role=Role.OWNER)
    return u


@pytest.fixture
def viewer(db, tenant):
    from django.contrib.auth import get_user_model

    u = get_user_model().objects.create_user(email="viewer@wandeedee.test", password="pw-123456789")
    Membership.objects.create(user=u, tenant=tenant, role=Role.VIEWER)
    return u


SETTINGS_PAGES = [
    "workspace:settings_hub",
    "workspace:settings_company",
    "workspace:settings_line",
    "workspace:settings_pipeline",
    "workspace:settings_numbering",
    "workspace:settings_members",
    "workspace:settings_billing",
    "workspace:system_status",
    "workspace:modules_status",
    "workspace:onboarding",
]


@pytest.mark.parametrize("name", SETTINGS_PAGES)
def test_settings_pages_render_for_owner(client, owner, name) -> None:
    client.force_login(owner)
    assert client.get(reverse(name)).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("name", SETTINGS_PAGES)
def test_settings_pages_redirect_anon(client, name) -> None:
    assert client.get(reverse(name)).status_code == 302


def test_edit_pages_forbidden_for_viewer(client, viewer) -> None:
    client.force_login(viewer)
    # hub/billing/status/members(GET)/onboarding are viewable; company/line/pipeline/numbering edit are not
    assert client.get(reverse("workspace:settings_company")).status_code == 403
    assert client.get(reverse("workspace:settings_line")).status_code == 403
    assert client.get(reverse("workspace:settings_pipeline")).status_code == 403
    # viewer can see the hub
    assert client.get(reverse("workspace:settings_hub")).status_code == 200


def test_member_invite_creates_user_and_membership(client, owner, tenant, mailoutbox) -> None:
    client.force_login(owner)
    resp = client.post(
        reverse("workspace:settings_members"),
        {
            "email": "newbie@wandeedee.test",
            "full_name": "น้องใหม่",
            "role": Role.SALES,
            "can_see_all_records": "on",
        },
    )
    assert resp.status_code == 302
    from django.contrib.auth import get_user_model

    u = get_user_model().objects.get(email="newbie@wandeedee.test")
    assert not u.has_usable_password()
    assert Membership.objects.filter(user=u, tenant=tenant, role=Role.SALES).exists()


def test_member_invite_forbidden_for_viewer(client, viewer) -> None:
    client.force_login(viewer)
    resp = client.post(
        reverse("workspace:settings_members"), {"email": "x@y.test", "role": Role.SALES}
    )
    assert resp.status_code == 403


def test_company_save(client, owner, tenant) -> None:
    client.force_login(owner)
    resp = client.post(
        reverse("workspace:settings_company"),
        {"name_th": "วันดีดี เฟอร์นิเจอร์ จำกัด", "branch_kind": "head"},
    )
    assert resp.status_code == 302
    from apps.tenants.models import CompanyProfile

    assert CompanyProfile.objects.get(tenant=tenant).name_th == "วันดีดี เฟอร์นิเจอร์ จำกัด"


def test_onboarding_step_navigation(client, owner) -> None:
    client.force_login(owner)
    for step in (1, 2, 3, 4, 5):
        resp = client.get(reverse("workspace:onboarding") + f"?step={step}")
        assert resp.status_code == 200
    # posting step 1 saves the company and advances
    resp = client.post(
        reverse("workspace:onboarding") + "?step=1", {"name_th": "ทดสอบ", "branch_kind": "head"}
    )
    assert resp.status_code == 302
    assert "step=2" in resp["Location"]


def test_onboarding_remaining_on_home(client, owner) -> None:
    client.force_login(owner)
    resp = client.get(reverse("core:home"))
    assert resp.status_code == 200
    assert resp.context["onboarding_remaining"] > 0


def test_public_home_renders_for_anon(client, tenant) -> None:
    # the per-tenant homepage is served at the tenant root host
    resp = client.get("/", HTTP_HOST=f"{tenant.slug}.localhost")
    assert resp.status_code == 200
    assert "ดูสินค้าทั้งหมด" in resp.content.decode()


def test_billing_page_shows_all_public_tiers(client, owner) -> None:
    client.force_login(owner)
    resp = client.get(reverse("workspace:settings_billing"))
    assert resp.status_code == 200
    body = resp.content.decode()
    for label in ("Starter", "Growth", "Pro", "Business"):
        assert label in body
    # Featured ribbon on Growth.
    assert "แนะนำ" in body


def test_plan_change_owner_updates_tenant(client, owner, tenant) -> None:
    client.force_login(owner)
    resp = client.post(reverse("workspace:plan_change"), {"plan": "growth", "cycle": "annual"})
    assert resp.status_code == 302
    tenant.refresh_from_db()
    assert tenant.plan == "growth"
    assert tenant.billing_cycle == "annual"

    from apps.audit.models import AuditEvent

    ev = AuditEvent.all_tenants.filter(action="tenant.plan_changed").latest("created_at")
    assert ev.changes["after"]["plan"] == "growth"
    assert ev.changes["before"]["plan"] == "trial"


def test_plan_change_viewer_forbidden(client, viewer, tenant) -> None:
    client.force_login(viewer)
    resp = client.post(reverse("workspace:plan_change"), {"plan": "growth", "cycle": "monthly"})
    assert resp.status_code == 403
    tenant.refresh_from_db()
    assert tenant.plan == "trial"


def test_plan_change_rejects_unknown_code(client, owner, tenant) -> None:
    client.force_login(owner)
    resp = client.post(reverse("workspace:plan_change"), {"plan": "enterprise", "cycle": "monthly"})
    assert resp.status_code == 302  # back to billing with an error message
    tenant.refresh_from_db()
    assert tenant.plan == "trial"


def test_modules_status_lists_core_and_plan_modules(client, owner) -> None:
    client.force_login(owner)
    resp = client.get(reverse("workspace:modules_status"))
    assert resp.status_code == 200
    body = resp.content.decode()
    # core always on
    assert "ลูกค้าและดีล (CRM)" in body
    assert "ใบเสนอราคา" in body
    # plan-gated visible
    assert "ระบบบัญชี" in body
    # future bucket present
    assert "ยังไม่พัฒนา" in body


def test_modules_status_forbidden_for_viewer(client, viewer) -> None:
    client.force_login(viewer)
    assert client.get(reverse("workspace:modules_status")).status_code == 403


def test_feature_override_force_on(tenant) -> None:
    """A FORCE_ON override grants a plan-gated feature on a tier that wouldn't normally have it."""
    from apps.tenants.features import feature_enabled
    from apps.tenants.models import FeatureOverrideMode, TenantFeatureOverride

    tenant.plan = "growth"
    tenant.save(update_fields=["plan"])
    assert feature_enabled(tenant, "billing") is False
    TenantFeatureOverride.objects.create(
        tenant=tenant,
        module_code="billing",
        mode=FeatureOverrideMode.FORCE_ON,
        reason="anchor customer — free billing for 6 months",
    )
    assert feature_enabled(tenant, "billing") is True


def test_feature_override_force_off(tenant) -> None:
    """A FORCE_OFF override hides a feature even when the plan would grant it."""
    from apps.tenants.features import feature_enabled
    from apps.tenants.models import FeatureOverrideMode, TenantFeatureOverride

    tenant.plan = "pro"
    tenant.save(update_fields=["plan"])
    assert feature_enabled(tenant, "billing") is True
    TenantFeatureOverride.objects.create(
        tenant=tenant,
        module_code="billing",
        mode=FeatureOverrideMode.FORCE_OFF,
        reason="customer in dispute — billing access suspended",
    )
    assert feature_enabled(tenant, "billing") is False


def test_feature_override_expired_ignored(tenant) -> None:
    """An expired override does not affect resolution; plan defaults apply."""
    from datetime import date, timedelta

    from apps.tenants.features import feature_enabled
    from apps.tenants.models import FeatureOverrideMode, TenantFeatureOverride

    tenant.plan = "growth"
    tenant.save(update_fields=["plan"])
    TenantFeatureOverride.objects.create(
        tenant=tenant,
        module_code="billing",
        mode=FeatureOverrideMode.FORCE_ON,
        reason="6-month trial",
        expires_at=date.today() - timedelta(days=1),
    )
    assert feature_enabled(tenant, "billing") is False


def test_platform_disabled_modules_wins_over_plan(tenant, settings) -> None:
    """PLATFORM_DISABLED_MODULES kills a feature for every tenant on every plan."""
    from apps.tenants.features import feature_enabled

    tenant.plan = "business"  # business normally has billing
    tenant.save(update_fields=["plan"])
    assert feature_enabled(tenant, "billing") is True
    settings.PLATFORM_DISABLED_MODULES = ["billing"]
    assert feature_enabled(tenant, "billing") is False


def test_platform_disabled_modules_wins_over_force_on_override(tenant, settings) -> None:
    """A FORCE_ON override cannot re-enable a feature the platform has killed."""
    from apps.tenants.features import feature_enabled
    from apps.tenants.models import FeatureOverrideMode, TenantFeatureOverride

    tenant.plan = "growth"
    tenant.save(update_fields=["plan"])
    TenantFeatureOverride.objects.create(
        tenant=tenant,
        module_code="billing",
        mode=FeatureOverrideMode.FORCE_ON,
        reason="anchor",
    )
    assert feature_enabled(tenant, "billing") is True
    settings.PLATFORM_DISABLED_MODULES = ["billing"]
    assert feature_enabled(tenant, "billing") is False


def test_billing_middleware_respects_override(client, tenant) -> None:
    """Growth tenant with a billing override can hit /billing/invoices/."""
    from django.contrib.auth import get_user_model

    from apps.accounts.models import Membership, Role
    from apps.tenants.models import FeatureOverrideMode, TenantFeatureOverride

    tenant.plan = "growth"
    tenant.save(update_fields=["plan"])
    TenantFeatureOverride.objects.create(
        tenant=tenant,
        module_code="billing",
        mode=FeatureOverrideMode.FORCE_ON,
        reason="anchor",
    )
    owner = get_user_model().objects.create_user(email="o@x.test", password="pw-123456789")
    Membership.objects.create(user=owner, tenant=tenant, role=Role.OWNER)
    client.force_login(owner)
    assert client.get(reverse("billing:invoices")).status_code == 200


def test_plan_change_cannot_switch_to_trial(client, owner, tenant) -> None:
    """Trial isn't a public tier — UI never offers it, view must reject too."""
    tenant.plan = "growth"
    tenant.save(update_fields=["plan"])
    client.force_login(owner)
    resp = client.post(reverse("workspace:plan_change"), {"plan": "trial", "cycle": "monthly"})
    assert resp.status_code == 302
    tenant.refresh_from_db()
    assert tenant.plan == "growth"
