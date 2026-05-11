"""Creating a Tenant seeds the default pipeline (apps/crm/signals.py + services.py)."""

from __future__ import annotations

import pytest

from apps.core.current_tenant import tenant_context
from apps.crm.models import PipelineStage, StageKind
from apps.crm.services import DEFAULT_PIPELINE_STAGES, seed_default_pipeline

pytestmark = pytest.mark.django_db


def test_new_tenant_gets_default_pipeline(tenant) -> None:
    with tenant_context(tenant):
        stages = list(PipelineStage.objects.order_by("order"))
    assert len(stages) == len(DEFAULT_PIPELINE_STAGES)
    assert [s.kind for s in stages][-2:] == [StageKind.WON, StageKind.LOST]


def test_pipeline_is_per_tenant(tenant, other_tenant) -> None:
    with tenant_context(tenant):
        assert PipelineStage.objects.count() == len(DEFAULT_PIPELINE_STAGES)
        first_a = PipelineStage.objects.first()
    with tenant_context(other_tenant):
        stages_b = list(PipelineStage.objects.all())
    assert first_a not in stages_b
    assert len(stages_b) == len(DEFAULT_PIPELINE_STAGES)


def test_seed_default_pipeline_is_idempotent(tenant) -> None:
    seed_default_pipeline(tenant)  # already seeded by the signal
    with tenant_context(tenant):
        assert PipelineStage.objects.count() == len(DEFAULT_PIPELINE_STAGES)
