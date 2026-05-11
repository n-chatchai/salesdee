"""Project-wide pytest fixtures."""

from __future__ import annotations

import pytest

from apps.core.current_tenant import tenant_context


@pytest.fixture
def tenant(db):
    from apps.tenants.models import Tenant

    return Tenant.objects.create(name="วันดีดี เฟอร์นิเจอร์", slug="wandeedee")


@pytest.fixture
def other_tenant(db):
    from apps.tenants.models import Tenant

    return Tenant.objects.create(name="ร้านเฟอร์นิเจอร์อื่น", slug="other-shop")


@pytest.fixture
def active_tenant(tenant):
    """Run the test body with `tenant` activated as the current tenant."""
    with tenant_context(tenant):
        yield tenant


@pytest.fixture
def user(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(
        email="sales@wandeedee.test", password="testpass-12345", full_name="พนักงานขาย ทดสอบ"
    )


@pytest.fixture
def membership(user, tenant):
    from apps.accounts.models import Membership, Role

    return Membership.objects.create(user=user, tenant=tenant, role=Role.SALES)
