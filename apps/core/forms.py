from __future__ import annotations

from typing import cast

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import QuerySet


def set_queryset(form: forms.BaseForm, name: str, queryset: QuerySet) -> None:
    """Re-bind a ModelChoiceField's queryset (per request).

    ModelForm binds FK querysets at class-definition time; for a FK to a TenantScopedModel that's
    an empty queryset (no tenant active at import). Always re-bind in the form's ``__init__``.
    See CLAUDE.md §5. (django-stubs types ``form.fields[...]`` as a plain ``Field``, hence the cast.)
    """
    cast("forms.ModelChoiceField", form.fields[name]).queryset = queryset


def tenant_users() -> QuerySet:
    """Active users who belong to the current tenant (for owner/assignee/salesperson pickers)."""
    from apps.core.current_tenant import get_current_tenant

    tenant = get_current_tenant()
    qs = get_user_model().objects.filter(is_active=True)
    if tenant is not None:
        qs = qs.filter(memberships__tenant=tenant, memberships__is_active=True)
    return qs.distinct()
