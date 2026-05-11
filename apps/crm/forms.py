from __future__ import annotations

from typing import cast

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from apps.core.current_tenant import get_current_tenant

from .models import Activity, Contact, Customer, Deal, Lead, PipelineStage, StageKind, Task

User = get_user_model()


def _tenant_users() -> QuerySet:
    tenant = get_current_tenant()
    qs = User.objects.filter(is_active=True)
    if tenant is not None:
        qs = qs.filter(memberships__tenant=tenant, memberships__is_active=True)
    return qs.distinct()


def _set_queryset(form: forms.BaseForm, name: str, queryset: QuerySet) -> None:
    """Set the queryset on a ModelChoiceField (django-stubs types form.fields[...] as plain Field)."""
    cast("forms.ModelChoiceField", form.fields[name]).queryset = queryset


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "name",
            "name_en",
            "kind",
            "tax_id",
            "branch_label",
            "billing_address",
            "shipping_address",
            "default_credit_days",
            "notes",
        ]
        widgets = {
            "billing_address": forms.Textarea(attrs={"rows": 2}),
            "shipping_address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class DealForm(forms.ModelForm):
    class Meta:
        model = Deal
        fields = [
            "name",
            "customer",
            "contact",
            "stage",
            "owner",
            "estimated_value",
            "expected_close_date",
            "channel",
            "source",
            "notes",
        ]
        widgets = {
            "expected_close_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ModelForm binds FK querysets at *class* definition time, which for a context-aware
        # TenantManager means "no tenant active" -> empty. Re-bind them per request.
        _set_queryset(self, "stage", PipelineStage.objects.all())
        _set_queryset(self, "customer", Customer.objects.all())
        _set_queryset(self, "contact", Contact.objects.all())
        _set_queryset(self, "owner", _tenant_users())
        for name in ("owner", "contact", "customer", "estimated_value"):
            self.fields[name].required = False
        self.fields["stage"].required = True
        self.fields["estimated_value"].initial = 0
        if self.instance.pk is None:
            self.fields["stage"].initial = (
                PipelineStage.objects.filter(kind=StageKind.OPEN).order_by("order").first()
            )

    def clean_estimated_value(self):
        return self.cleaned_data.get("estimated_value") or 0


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ["kind", "body", "contact"]
        widgets = {"body": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, customer: Customer | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contact"].required = False
        _set_queryset(
            self,
            "contact",
            Contact.objects.filter(customer=customer)
            if customer is not None
            else Contact.objects.none(),
        )


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["kind", "description", "due_at", "assignee"]
        widgets = {"due_at": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _set_queryset(self, "assignee", _tenant_users())
        self.fields["assignee"].required = False


class LeadForm(forms.ModelForm):
    """Internal manual lead entry / edit."""

    class Meta:
        model = Lead
        fields = [
            "name",
            "company_name",
            "phone",
            "email",
            "line_id",
            "channel",
            "source",
            "product_interest",
            "budget",
            "message",
            "status",
            "assigned_to",
        ]
        widgets = {"message": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _set_queryset(self, "assigned_to", _tenant_users())
        self.fields["assigned_to"].required = False
        self.fields["budget"].required = False


class LeadIntakeForm(forms.ModelForm):
    """Public-facing 'request a quote / contact us' form. No internal fields."""

    class Meta:
        model = Lead
        fields = [
            "name",
            "company_name",
            "phone",
            "email",
            "line_id",
            "product_interest",
            "budget",
            "message",
        ]
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["budget"].required = False
        self.fields["name"].required = True
