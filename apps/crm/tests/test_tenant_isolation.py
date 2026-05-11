"""Tenant isolation for CRM models. The pattern here applies to every TenantScopedModel
(CLAUDE.md §5, §8 Definition of Done): data created under one tenant must be invisible from
another tenant's context, and saving without a tenant context must fail.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.core.current_tenant import tenant_context
from apps.crm.models import Customer

pytestmark = pytest.mark.django_db


def test_customer_invisible_from_other_tenant(tenant, other_tenant) -> None:
    with tenant_context(tenant):
        Customer.objects.create(name="ลูกค้า A")
        assert Customer.objects.count() == 1

    with tenant_context(other_tenant):
        assert Customer.objects.count() == 0
        Customer.objects.create(name="ลูกค้า B")
        assert Customer.objects.count() == 1

    with tenant_context(tenant):
        assert list(Customer.objects.values_list("name", flat=True)) == ["ลูกค้า A"]


def test_save_without_tenant_context_raises(db) -> None:
    with pytest.raises(RuntimeError):
        Customer.objects.create(name="ไม่มี tenant")


def test_no_tenant_context_yields_no_rows(tenant) -> None:
    with tenant_context(tenant):
        Customer.objects.create(name="ลูกค้า A")
    # outside any tenant context the scoped manager fails closed
    assert Customer.objects.count() == 0


def test_rls_policy_exists_on_crm_tables(db) -> None:
    """The RLS migration must have created a policy + enabled RLS on each crm tenant table."""
    expected = {
        "crm_customer",
        "crm_contact",
        "crm_pipelinestage",
        "crm_deal",
        "crm_activity",
        "crm_task",
    }
    with connection.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_policies WHERE policyname = 'tenant_isolation'")
        with_policy = {row[0] for row in cur.fetchall()}
        cur.execute("SELECT relname FROM pg_class WHERE relrowsecurity AND relkind = 'r'")
        with_rls = {row[0] for row in cur.fetchall()}
    assert expected <= with_policy
    assert expected <= with_rls
