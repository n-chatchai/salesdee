from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_signup_creates_tenant_and_logs_in(client) -> None:
    from apps.accounts.models import Membership, Role
    from apps.catalog.models import ProductCategory  # noqa: F401  (ensure app loaded)
    from apps.core.current_tenant import tenant_context
    from apps.crm.models import PipelineStage
    from apps.tenants.models import CompanyProfile, Tenant

    resp = client.post(
        reverse("accounts:signup"),
        {
            "workspace_name": "ร้านโต๊ะดี",
            "slug": "rantodee",
            "full_name": "เจ้าของ ร้าน",
            "email": "owner@rantodee.test",
            "password": "sup3r-secret-pw-99",
        },
    )
    assert resp.status_code == 302
    tenant = Tenant.objects.get(slug="rantodee")
    assert CompanyProfile.objects.filter(tenant=tenant).exists()
    user = get_user_model().objects.get(email="owner@rantodee.test")
    m = Membership.objects.get(user=user, tenant=tenant)
    assert m.role == Role.OWNER
    with tenant_context(tenant):
        assert PipelineStage.objects.exists()
    # logged in
    assert client.get("/").status_code in (200, 302)


def test_signup_rejects_duplicate_slug(client, tenant) -> None:
    resp = client.post(
        reverse("accounts:signup"),
        {
            "workspace_name": "อีกร้าน",
            "slug": tenant.slug,
            "full_name": "x y",
            "email": "x@y.test",
            "password": "sup3r-secret-pw-99",
        },
    )
    assert resp.status_code == 200
    assert b"\xe0" in resp.content  # form re-rendered with an error (Thai bytes present)


def test_password_reset_sends_email(client, user) -> None:
    resp = client.post(reverse("accounts:password_reset"), {"email": user.email})
    assert resp.status_code == 302
    assert len(mail.outbox) == 1
    assert user.email in mail.outbox[0].to


def test_password_change_requires_login(client) -> None:
    assert client.get(reverse("accounts:password_change")).status_code == 302


def test_password_change_works(client, user) -> None:
    client.force_login(user)
    resp = client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "testpass-12345",
            "new_password1": "an0ther-Strong-pw",
            "new_password2": "an0ther-Strong-pw",
        },
    )
    assert resp.status_code == 302
    user.refresh_from_db()
    assert user.check_password("an0ther-Strong-pw")
