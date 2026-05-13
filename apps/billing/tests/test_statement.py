from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import services
from apps.core.current_tenant import tenant_context
from apps.crm.models import Customer
from apps.quotes.models import DocStatus, DocType, LineType, SalesDocLine, SalesDocument

pytestmark = pytest.mark.django_db


def _make_invoice(tenant, customer, *, qty=1, price=Decimal("1000")) -> SalesDocument:
    with tenant_context(tenant):
        q = SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            customer=customer,
            issue_date=date.today(),
            status=DocStatus.ACCEPTED,
        )
        SalesDocLine.objects.create(
            document=q,
            line_type=LineType.ITEM,
            description="ของ",
            quantity=qty,
            unit_price=price,
            tax_type="vat7",
        )
        return services.create_invoice_from_quotation(q)


def test_customer_statement_totals_reconcile(tenant) -> None:
    with tenant_context(tenant):
        cust = Customer.objects.create(name="ลูกค้าสรุปยอด")
    _make_invoice(tenant, cust, qty=1, price=Decimal("1000"))  # 1070 incl VAT
    _make_invoice(tenant, cust, qty=2, price=Decimal("500"))  # 1070 incl VAT
    with tenant_context(tenant):
        data = services.customer_statement(cust)
    # 2 open invoices, nothing paid
    assert len(data["invoices"]) == 2
    assert data["outstanding"] == Decimal("2140.00")
    # aging total == grand outstanding
    aging_sum = sum(data["aging"].values())
    assert aging_sum == data["outstanding"]
    # paid + outstanding == issued
    assert data["total_issued"] == data["total_paid"] + data["outstanding"]


def test_customer_statement_view_renders(client, tenant, user, membership) -> None:
    with tenant_context(tenant):
        cust = Customer.objects.create(name="ลูกค้า ABC")
    _make_invoice(tenant, cust)
    client.force_login(user)
    resp = client.get(f"/billing/customers/{cust.pk}/statement/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "ใบแจ้งยอด" in body
    assert cust.name in body
