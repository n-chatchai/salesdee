from __future__ import annotations

from typing import cast

from django import forms
from django.db.models import QuerySet


def set_queryset(form: forms.BaseForm, name: str, queryset: QuerySet) -> None:
    """Re-bind a ModelChoiceField's queryset (per request).

    ModelForm binds FK querysets at class-definition time; for a FK to a TenantScopedModel that's
    an empty queryset (no tenant active at import). Always re-bind in the form's ``__init__``.
    See CLAUDE.md §5. (django-stubs types ``form.fields[...]`` as a plain ``Field``, hence the cast.)
    """
    cast("forms.ModelChoiceField", form.fields[name]).queryset = queryset
