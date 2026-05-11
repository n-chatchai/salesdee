"""Shared admin helpers.

``TenantScopedAdmin`` — base ModelAdmin for ``TenantScopedModel`` subclasses. Django admin
requests go through ``CurrentTenantMiddleware`` which activates the staff user's own tenant,
so the model's default (scoped) manager would only show that tenant's rows. Platform admins
need to see across tenants, so this base reads via the unscoped ``all_tenants`` manager and
surfaces the ``tenant`` column / filter.
"""

from __future__ import annotations

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest


class TenantScopedAdmin(admin.ModelAdmin):
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return self.model.all_tenants.get_queryset()

    def get_list_display(self, request: HttpRequest):
        base = list(super().get_list_display(request))
        return [*base, "tenant"] if "tenant" not in base else base

    def get_list_filter(self, request: HttpRequest):
        base = list(super().get_list_filter(request))
        return ["tenant", *base] if "tenant" not in base else base
