from __future__ import annotations

import pytest
from django.core.management import call_command

from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def test_seed_demo_populates_a_fresh_tenant(db) -> None:
    call_command("seed_demo", "--tenant", "demo-test")
    from apps.catalog.models import Product
    from apps.crm.models import Customer, Deal, Lead
    from apps.quotes.models import SalesDocument
    from apps.tenants.models import CompanyProfile, Tenant

    t = Tenant.objects.get(slug="demo-test")
    with tenant_context(t):
        assert Customer.objects.count() == 4
        assert Product.objects.count() == 10
        assert Deal.objects.count() == 5
        assert Lead.objects.count() == 3
        assert SalesDocument.objects.count() == 1  # one quotation, with lines
        q = SalesDocument.objects.get()
        assert q.lines.count() == 7
        assert CompanyProfile.objects.get(tenant=t).tax_id == "0125565099999"

    # second run without --force is a no-op
    call_command("seed_demo", "--tenant", "demo-test")
    with tenant_context(t):
        assert Customer.objects.count() == 4
