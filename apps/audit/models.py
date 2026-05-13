"""Audit log (REQUIREMENTS.md §4.15 FR-15.5).

One row per significant tenant-scoped action — who did what to which object, with optional
before/after summary. Used for forensics + the in-app "settings → audit" view.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TenantScopedModel


class AuditEvent(TenantScopedModel):
    """A recorded action. ``action`` is a dotted string like ``quotation.sent``."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="ผู้กระทำ",
    )
    action = models.CharField("การกระทำ", max_length=80, db_index=True)
    object_type = models.CharField("ชนิดวัตถุ", max_length=80, blank=True)
    object_id = models.PositiveBigIntegerField("รหัสวัตถุ", null=True, blank=True)
    object_repr = models.CharField("วัตถุ", max_length=255, blank=True)
    changes = models.JSONField("รายละเอียดการเปลี่ยนแปลง", default=dict, blank=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "บันทึกตรวจสอบ"
        verbose_name_plural = "บันทึกตรวจสอบ"
        indexes = [models.Index(fields=["action", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.action} · {self.object_repr or self.object_type}"
