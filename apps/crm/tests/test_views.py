from __future__ import annotations

import pytest
from django.urls import reverse

from apps.core.current_tenant import tenant_context
from apps.crm.models import Deal, DealStatus, PipelineStage, StageKind

pytestmark = pytest.mark.django_db


def _open_stages(tenant):
    with tenant_context(tenant):
        return list(PipelineStage.objects.filter(kind=StageKind.OPEN).order_by("order"))


def test_pipeline_requires_login(client) -> None:
    resp = client.get(reverse("crm:pipeline"))
    assert resp.status_code == 302


def test_pipeline_renders_with_deal(client, user, membership, tenant) -> None:
    stages = _open_stages(tenant)
    with tenant_context(tenant):
        Deal.objects.create(name="ตู้บานเลื่อน ออฟฟิศ A", stage=stages[0], estimated_value=120000)
    client.force_login(user)
    resp = client.get(reverse("crm:pipeline"))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "ตู้บานเลื่อน ออฟฟิศ A" in body
    assert stages[0].name in body


def test_move_deal_changes_stage(client, user, membership, tenant) -> None:
    stages = _open_stages(tenant)
    with tenant_context(tenant):
        deal = Deal.objects.create(name="ดีลทดสอบ", stage=stages[0])
    client.force_login(user)
    resp = client.post(reverse("crm:move_deal"), {"deal_id": deal.pk, "stage_id": stages[1].pk})
    assert resp.status_code == 204
    with tenant_context(tenant):
        deal.refresh_from_db()
        assert deal.stage_id == stages[1].pk


def test_move_deal_to_won_stage_marks_won(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        open_stage = PipelineStage.objects.filter(kind=StageKind.OPEN).order_by("order")[0]
        won_stage = PipelineStage.objects.filter(kind=StageKind.WON)[0]
        deal = Deal.objects.create(name="ปิดงาน", stage=open_stage)
    client.force_login(user)
    client.post(reverse("crm:move_deal"), {"deal_id": deal.pk, "stage_id": won_stage.pk})
    with tenant_context(tenant):
        deal.refresh_from_db()
        assert deal.status == DealStatus.WON
        assert deal.closed_at is not None


def test_move_deal_from_other_tenant_is_404(client, user, membership, tenant, other_tenant) -> None:
    with tenant_context(other_tenant):
        other_stage = PipelineStage.objects.filter(kind=StageKind.OPEN).order_by("order")[0]
        other_deal = Deal.objects.create(name="ดีลของอีกบริษัท", stage=other_stage)
    with tenant_context(tenant):
        my_stage = PipelineStage.objects.filter(kind=StageKind.OPEN).order_by("order")[0]
    client.force_login(user)  # belongs to `tenant`
    resp = client.post(
        reverse("crm:move_deal"), {"deal_id": other_deal.pk, "stage_id": my_stage.pk}
    )
    assert resp.status_code == 404


def test_customer_list_renders(client, user, membership) -> None:
    client.force_login(user)
    resp = client.get(reverse("crm:customers"))
    assert resp.status_code == 200
    assert "ลูกค้า" in resp.content.decode()
