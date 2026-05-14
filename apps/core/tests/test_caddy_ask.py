"""Caddy on-demand-TLS ``ask`` endpoint — gates which hostnames we'll mint a cert for."""

from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _ask(client, domain: str = "", **extra):
    url = reverse("core:caddy_ask")
    if domain:
        url += f"?domain={domain}"
    return client.get(url, **extra)


def test_platform_host_allowed(client) -> None:
    assert _ask(client, "localhost").status_code == 200


def test_built_in_subdomain_allowed(client, tenant) -> None:
    assert _ask(client, f"{tenant.slug}.localhost").status_code == 200


def test_built_in_subdomain_unknown_slug_404(client, tenant) -> None:
    assert _ask(client, "nope.localhost").status_code == 404


def test_verified_tenant_domain_allowed(client, tenant) -> None:
    from apps.tenants.models import TenantDomain

    TenantDomain.objects.create(tenant=tenant, domain="wandeedee.test", verified=True)
    assert _ask(client, "wandeedee.test").status_code == 200


def test_unverified_tenant_domain_404(client, tenant) -> None:
    from apps.tenants.models import TenantDomain

    TenantDomain.objects.create(tenant=tenant, domain="pending.test", verified=False)
    assert _ask(client, "pending.test").status_code == 404


def test_unknown_domain_404(client) -> None:
    assert _ask(client, "evil.example.com").status_code == 404


def test_missing_domain_param_400(client) -> None:
    assert _ask(client, "").status_code == 400
