from __future__ import annotations

import pytest

from apps.core.current_tenant import tenant_context
from apps.integrations.line import LineNotConfigured, line_is_configured, push_text
from apps.integrations.models import LineIntegration

pytestmark = pytest.mark.django_db


def test_line_integration_tenant_isolation(tenant, other_tenant) -> None:
    with tenant_context(tenant):
        LineIntegration.objects.create(channel_access_token="tok")
        assert LineIntegration.objects.count() == 1
        assert line_is_configured() is True
    with tenant_context(other_tenant):
        assert LineIntegration.objects.count() == 0
        assert line_is_configured() is False


def test_push_text_without_integration_raises(tenant) -> None:
    with tenant_context(tenant), pytest.raises(LineNotConfigured):
        push_text("Uabc123", "hi")


def test_tokenless_or_inactive_integration_is_not_configured(tenant) -> None:
    with tenant_context(tenant):
        integ = LineIntegration.objects.create(channel_access_token="", is_active=True)
        assert line_is_configured() is False
        integ.channel_access_token = "tok"
        integ.is_active = False
        integ.save()
        assert line_is_configured() is False
