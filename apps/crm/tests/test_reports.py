from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def _make_manager(membership) -> None:
    from apps.accounts.models import Role

    membership.role = Role.MANAGER
    membership.save()


def test_reports_requires_a_manager(client, user, membership, tenant) -> None:
    client.force_login(user)  # membership is SALES by default
    assert client.get(reverse("crm:reports")).status_code == 403
    _make_manager(membership)
    assert client.get(reverse("crm:reports")).status_code == 200


def test_reports_page(client, user, membership, tenant) -> None:
    from apps.crm.models import Deal, DealStatus, Lead, LeadChannel, SalesTarget
    from apps.quotes.models import DocStatus, DocType, SalesDocument

    _make_manager(membership)
    today = date.today()
    with tenant_context(tenant):
        Deal.objects.create(
            name="วอน",
            owner=user,
            estimated_value=Decimal("100000"),
            status=DealStatus.WON,
            closed_at=timezone.now(),
            channel=LeadChannel.LINE,
        )
        Deal.objects.create(
            name="แพ้",
            owner=user,
            estimated_value=Decimal("20000"),
            status=DealStatus.LOST,
            closed_at=timezone.now(),
            lost_reason="ราคาสูงเกินไป",
        )
        Lead.objects.create(name="ลีดทางไลน์", channel=LeadChannel.LINE)
        SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            issue_date=today,
            status=DocStatus.SENT,
            salesperson=user,
            doc_number="QT-A",
        )
        SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            issue_date=today,
            status=DocStatus.ACCEPTED,
            salesperson=user,
            doc_number="QT-B",
        )
        SalesTarget.objects.create(
            salesperson=user, year=today.year, month=today.month, amount=Decimal("500000")
        )
    client.force_login(user)
    body = client.get(reverse("crm:reports")).content.decode()
    assert "รายงานการขาย" in body
    assert user.get_full_name() in body
    assert "100000" in body  # won value
    assert "50%" in body  # quote conversion: 1 accepted of 2 "sent"
    assert "500000" in body  # this month's target
    assert "ราคาสูงเกินไป" in body  # lost-reason breakdown


def test_reports_xlsx_export(client, user, membership, tenant) -> None:
    from apps.crm.models import Deal, DealStatus

    _make_manager(membership)
    with tenant_context(tenant):
        Deal.objects.create(
            name="w",
            owner=user,
            estimated_value=Decimal("1000"),
            status=DealStatus.WON,
            closed_at=timezone.now(),
        )
    client.force_login(user)
    resp = client.get(reverse("crm:reports") + "?export=xlsx")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp["Content-Type"]
    assert resp.content[:2] == b"PK"  # xlsx is a zip


def test_sales_target_tenant_isolation(tenant, other_tenant) -> None:
    from apps.crm.models import SalesTarget

    with tenant_context(tenant):
        SalesTarget.objects.create(year=2026, month=5, amount=Decimal("1"))
        assert SalesTarget.objects.count() == 1
    with tenant_context(other_tenant):
        assert SalesTarget.objects.count() == 0
