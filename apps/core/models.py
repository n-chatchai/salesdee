"""Shared model base classes. Read CLAUDE.md §4–§5 before changing.

- ``BaseModel``         — created_at / updated_at; for *global* models (Tenant, User, platform config).
- ``TenantScopedModel`` — adds a ``tenant`` FK + auto-scoped manager; for everything tenant-owned.
  Its default manager (``objects``) filters every queryset to the current tenant. Use
  ``Model.all_tenants`` only with a justification comment (migrations, platform admin, tasks that
  already activated a tenant).
"""

from __future__ import annotations

from django.db import models

from .current_tenant import get_current_tenant


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        get_latest_by = "created_at"


class AllTenantsManager(models.Manager):
    """Unscoped manager. Bypasses tenant filtering — use sparingly and comment why."""


class TenantManager(models.Manager):
    """Default manager for tenant-scoped models: filters to the current tenant.

    If no tenant is active, returns an empty queryset (fail closed) rather than
    leaking every tenant's rows.
    """

    def get_queryset(self) -> models.QuerySet:
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant is None:
            return qs.none()
        return qs.filter(tenant=tenant)


class TenantScopedModel(BaseModel):
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="+",
        editable=False,
        db_index=True,
    )

    objects = TenantManager()
    all_tenants = AllTenantsManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.tenant_id is None:
            tenant = get_current_tenant()
            if tenant is None:
                raise RuntimeError(
                    f"Cannot save {type(self).__name__} without an active tenant. "
                    "Activate one (request middleware or tenant_context()) first."
                )
            self.tenant = tenant
        super().save(*args, **kwargs)
