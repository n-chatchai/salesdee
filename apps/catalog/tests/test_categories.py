from __future__ import annotations

import pytest
from django.urls import reverse

from apps.catalog.models import ProductCategory
from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def test_categories_list_renders(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        ProductCategory.objects.create(name="โต๊ะ", order=1)
    client.force_login(user)
    resp = client.get(reverse("catalog:categories"))
    assert resp.status_code == 200
    assert "โต๊ะ" in resp.content.decode()


def test_categories_requires_login(client) -> None:
    resp = client.get(reverse("catalog:categories"))
    assert resp.status_code == 302


def test_category_create_edit_delete(client, user, membership, tenant) -> None:
    client.force_login(user)
    resp = client.post(reverse("catalog:category_create"), {"name": "เก้าอี้", "order": "2"})
    assert resp.status_code == 302
    with tenant_context(tenant):
        cat = ProductCategory.objects.get(name="เก้าอี้")
    # edit
    resp = client.post(
        reverse("catalog:category_edit", args=[cat.pk]), {"name": "เก้าอี้สำนักงาน", "order": "3"}
    )
    assert resp.status_code == 302
    with tenant_context(tenant):
        cat.refresh_from_db()
        assert cat.name == "เก้าอี้สำนักงาน"
    # delete
    resp = client.post(reverse("catalog:category_delete", args=[cat.pk]))
    assert resp.status_code == 302
    with tenant_context(tenant):
        assert not ProductCategory.objects.filter(pk=cat.pk).exists()


def test_public_catalog_match_fallback_when_ai_off(client, tenant, settings) -> None:
    settings.ANTHROPIC_API_KEY = ""
    resp = client.post(reverse("public_catalog_match", args=[tenant.slug]), {"q": "โต๊ะ 1.2 เมตร"})
    assert resp.status_code == 200
    # fallback block rendered (no AI), not a 500
    body = resp.content.decode()
    assert "ติดต่อ" in body or "ทีมงาน" in body or "match-results" not in body
