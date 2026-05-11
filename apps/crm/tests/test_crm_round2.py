from __future__ import annotations

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context
from apps.crm.models import (
    Activity,
    Customer,
    Deal,
    DealStatus,
    PipelineStage,
    StageKind,
    Task,
    TaskStatus,
)

pytestmark = pytest.mark.django_db


def test_new_tenant_gets_company_profile(tenant) -> None:
    from apps.tenants.models import CompanyProfile

    profile = CompanyProfile.objects.get(tenant=tenant)
    assert profile.name_th == tenant.name


def test_deal_create_sets_stage_and_probability(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        stage = PipelineStage.objects.filter(kind=StageKind.OPEN).order_by("order")[0]
    client.force_login(user)
    resp = client.post(reverse("crm:deal_create"), {"name": "โต๊ะผู้บริหาร x10", "stage": stage.pk})
    assert resp.status_code == 302
    with tenant_context(tenant):
        deal = Deal.objects.get(name="โต๊ะผู้บริหาร x10")
        assert deal.stage_id == stage.pk
        assert deal.probability == stage.default_probability
        assert deal.estimated_value == 0
        assert deal.status == DealStatus.OPEN
    assert resp.url == reverse("crm:deal_detail", args=[deal.pk])


def test_customer_create_then_detail(client, user, membership, tenant) -> None:
    client.force_login(user)
    resp = client.post(
        reverse("crm:customer_create"),
        {"name": "บริษัท ลูกค้า จำกัด", "kind": "company", "default_credit_days": 30},
    )
    assert resp.status_code == 302
    with tenant_context(tenant):
        c = Customer.objects.get(name="บริษัท ลูกค้า จำกัด")
    detail = client.get(reverse("crm:customer_detail", args=[c.pk]))
    assert detail.status_code == 200
    assert "บริษัท ลูกค้า จำกัด" in detail.content.decode()


def test_deal_log_activity_via_htmx(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        stage = PipelineStage.objects.filter(kind=StageKind.OPEN).order_by("order")[0]
        deal = Deal.objects.create(name="ดีลทดสอบ", stage=stage)
    client.force_login(user)
    resp = client.post(
        reverse("crm:deal_log_activity", args=[deal.pk]), {"kind": "call", "body": "โทรคุยแล้ว สนใจ"}
    )
    assert resp.status_code == 200
    assert "โทรคุยแล้ว สนใจ" in resp.content.decode()
    with tenant_context(tenant):
        assert deal.activities.count() == 1
        assert Activity.objects.get(deal=deal).created_by_id == user.pk


def test_deal_add_task_via_htmx(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        stage = PipelineStage.objects.filter(kind=StageKind.OPEN).order_by("order")[0]
        deal = Deal.objects.create(name="ดีลทดสอบ", stage=stage)
    client.force_login(user)
    resp = client.post(
        reverse("crm:deal_add_task", args=[deal.pk]),
        {"kind": "follow_up", "description": "ตามใบเสนอราคา", "assignee": user.pk},
    )
    assert resp.status_code == 200
    with tenant_context(tenant):
        assert deal.tasks.count() == 1


def test_task_list_and_mark_done(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        task = Task.objects.create(description="โทรกลับลูกค้า", assignee=user, kind="callback")
    client.force_login(user)
    listing = client.get(reverse("crm:tasks"))
    assert listing.status_code == 200
    assert "โทรกลับลูกค้า" in listing.content.decode()
    done = client.post(reverse("crm:task_done", args=[task.pk]))
    assert done.status_code == 200
    with tenant_context(tenant):
        task.refresh_from_db()
        assert task.status == TaskStatus.DONE
        assert task.completed_at is not None
