"""External integrations.  Spec: REQUIREMENTS.md §4.16.

Phase 1: LINE Official Account (receive/send messages, send documents, customer notifications) +
email (in/out). Stores per-tenant LINE channel credentials and (later) a unified Message log.
Phase 3: public REST API / webhooks; export/sync to accounting software (FlowAccount/PEAK/Express).

Tenant-owned config (e.g. LineIntegration) → ``TenantScopedModel`` (+ add ``enable_tenant_rls``).
"""

from __future__ import annotations

from django.db import models

from apps.core.models import TenantScopedModel


class LineIntegration(TenantScopedModel):
    """A tenant's LINE Official Account Messaging-API credentials. One per tenant.

    ``channel_access_token`` is a long-lived channel access token (used to push messages);
    ``channel_secret`` verifies inbound webhook signatures (inbound handling is a later task).
    TODO: encrypt these at rest (NFR §7) — for now they live in a plaintext config row that only
    platform/owner admins touch.
    """

    channel_id = models.CharField("Channel ID", max_length=50, blank=True)
    channel_secret = models.CharField("Channel secret", max_length=100, blank=True)
    channel_access_token = models.TextField("Channel access token", blank=True)
    is_active = models.BooleanField("เปิดใช้งาน", default=True)

    class Meta:
        verbose_name = "การเชื่อม LINE OA"
        verbose_name_plural = "การเชื่อม LINE OA"
        constraints = [
            models.UniqueConstraint(fields=["tenant"], name="uniq_line_integration_per_tenant")
        ]

    def __str__(self) -> str:
        return f"LINE OA {self.channel_id or self.tenant_id}"
