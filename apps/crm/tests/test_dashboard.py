from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.core.current_tenant import tenant_context

pytestmark = pytest.mark.django_db


def test_dashboard_renders_with_data(client, user, membership, tenant) -> None:
    from apps.crm.models import Deal, DealStatus, Lead, Task, TaskKind, TaskStatus
    from apps.quotes.models import DocStatus, DocType, SalesDocument

    with tenant_context(tenant):
        Deal.objects.create(
            name="ดีลเปิดอยู่", estimated_value=Decimal("50000"), probability=40, status=DealStatus.OPEN
        )
        Deal.objects.create(
            name="ดีลปิดได้",
            estimated_value=Decimal("30000"),
            status=DealStatus.WON,
            closed_at=timezone.now(),
        )
        Deal.objects.create(
            name="ดีลแพ้",
            estimated_value=Decimal("10000"),
            status=DealStatus.LOST,
            closed_at=timezone.now(),
            lost_reason="ราคาสูงไป",
        )
        Task.objects.create(
            assignee=user,
            status=TaskStatus.OPEN,
            kind=TaskKind.FOLLOW_UP,
            description="ตามดีลเปิดอยู่",
            due_at=timezone.now(),
        )
        Lead.objects.create(name="ลีดใหม่เอี่ยม")
        SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            issue_date=date.today(),
            status=DocStatus.SENT,
            doc_number="QT-2569-9001",
            sent_at=timezone.now(),
        )
        SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            issue_date=date.today(),
            status=DocStatus.SENT,
            doc_number="QT-2569-9002",
            valid_until=date.today() + timedelta(days=3),
        )
    client.force_login(user)
    body = client.get("/").content.decode()
    assert "แดชบอร์ด" in body
    assert "QT-2569-9001" in body  # sent, awaiting a response
    assert "QT-2569-9002" in body  # expiring within 7 days
    assert "ราคาสูงไป" in body  # lost-reason breakdown
    assert "ตามดีลเปิดอยู่" in body  # my open task
    assert "ลีดใหม่เอี่ยม" in body


def test_dashboard_for_user_without_a_workspace(client, db) -> None:
    from django.contrib.auth import get_user_model

    u = get_user_model().objects.create_user(
        email="lonely@example.test", password="testpass-12345", full_name="ไร้สังกัด"
    )
    client.force_login(u)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "ยังไม่ได้ผูกผู้ใช้นี้กับ workspace" in resp.content.decode()
