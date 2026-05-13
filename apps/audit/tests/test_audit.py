from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.audit.models import AuditEvent
from apps.audit.services import record
from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def test_record_creates_a_row_under_active_tenant(tenant, user) -> None:
    with tenant_context(tenant):
        ev = record(user, action="test.event", object_type="Thing", object_repr="x")
    assert ev is not None
    assert ev.tenant_id == tenant.pk
    assert ev.action == "test.event"
    assert ev.actor_id == user.pk


def test_record_noops_without_active_tenant(user) -> None:
    assert record(user, action="test.event") is None


def test_event_invisible_from_other_tenant(tenant, other_tenant, user) -> None:
    with tenant_context(tenant):
        record(user, action="a", object_repr="x")
        assert AuditEvent.objects.count() == 1
    with tenant_context(other_tenant):
        assert AuditEvent.objects.count() == 0
        record(user, action="b", object_repr="y")
        assert AuditEvent.objects.count() == 1
    with tenant_context(tenant):
        assert list(AuditEvent.objects.values_list("action", flat=True)) == ["a"]


def test_audit_log_view_requires_manager(client, user, tenant) -> None:
    from apps.accounts.models import Membership, Role

    Membership.objects.create(user=user, tenant=tenant, role=Role.SALES)
    client.force_login(user)
    assert client.get("/audit/").status_code == 403


def test_audit_log_view_shows_events_for_manager(client, tenant) -> None:
    from django.contrib.auth import get_user_model

    from apps.accounts.models import Membership, Role

    mgr = get_user_model().objects.create_user(
        email="mgr@wandeedee.test", password="x-12345678", full_name="ผู้จัดการ"
    )
    Membership.objects.create(user=mgr, tenant=tenant, role=Role.MANAGER)
    with tenant_context(tenant):
        record(mgr, action="quotation.sent", object_repr="QT-2569-0001")
    client.force_login(mgr)
    resp = client.get("/audit/")
    assert resp.status_code == 200
    assert b"QT-2569-0001" in resp.content


def test_issue_tax_invoice_records_audit_event(tenant, user) -> None:
    from apps.billing import services
    from apps.crm.models import Customer
    from apps.quotes.models import DocStatus, DocType, LineType, SalesDocLine, SalesDocument

    with tenant_context(tenant):
        cust = Customer.objects.create(name="ลูกค้าทดสอบ")
        q = SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            customer=cust,
            issue_date=date.today(),
            status=DocStatus.ACCEPTED,
        )
        SalesDocLine.objects.create(
            document=q,
            line_type=LineType.ITEM,
            description="ของ",
            quantity=1,
            unit_price=Decimal("1000"),
            tax_type="vat7",
        )
        inv = services.create_invoice_from_quotation(q, user=user)
        services.issue_tax_invoice(inv, user=user)
        assert AuditEvent.objects.filter(action="tax_invoice.issued").exists()
