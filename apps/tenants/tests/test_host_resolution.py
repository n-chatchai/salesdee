"""Host-based tenant resolution: subdomain <slug>.<APP_DOMAIN> and verified custom domains
(apps/core/middleware.py). APP_DOMAIN defaults to 'localhost' in dev/test."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import Membership, Role
from apps.core.middleware import CurrentTenantMiddleware
from apps.tenants.models import TenantDomain

pytestmark = pytest.mark.django_db


def _resolve_host(host: str):
    return CurrentTenantMiddleware._tenant_from_host(host)


def test_platform_host_resolves_no_tenant(tenant) -> None:
    assert _resolve_host("localhost") is None
    assert _resolve_host("app.localhost") is None


def test_subdomain_resolves_tenant(tenant) -> None:
    # the `tenant` fixture has slug "wandeedee"
    assert _resolve_host("wandeedee.localhost") == tenant
    assert _resolve_host("nope.localhost") is None
    # only one label deep
    assert _resolve_host("a.b.localhost") is None


def test_verified_custom_domain_resolves_tenant(tenant) -> None:
    TenantDomain.objects.create(tenant=tenant, domain="CRM.Wandeedee.com", verified=True)
    assert _resolve_host("crm.wandeedee.com") == tenant  # stored lowercased


def test_unverified_custom_domain_does_not_resolve(tenant) -> None:
    TenantDomain.objects.create(tenant=tenant, domain="staging.example.com", verified=False)
    assert _resolve_host("staging.example.com") is None


def test_custom_domain_of_inactive_tenant_does_not_resolve(tenant) -> None:
    TenantDomain.objects.create(tenant=tenant, domain="x.example.com", verified=True)
    tenant.is_active = False
    tenant.save()
    assert _resolve_host("x.example.com") is None


def test_member_on_tenant_subdomain_gets_that_tenant(client, user, membership, tenant) -> None:
    client.force_login(user)
    resp = client.get("/", HTTP_HOST="wandeedee.localhost")
    assert resp.status_code == 200
    assert resp.wsgi_request.tenant == tenant


def test_non_member_on_tenant_subdomain_is_forbidden(client, tenant, other_tenant) -> None:
    other = get_user_model().objects.create_user(email="b@x.test", password="pw-123456789")
    Membership.objects.create(user=other, tenant=other_tenant, role=Role.SALES)
    client.force_login(other)
    resp = client.get("/", HTTP_HOST="wandeedee.localhost")
    assert resp.status_code == 403
