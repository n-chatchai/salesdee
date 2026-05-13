from __future__ import annotations

from django import forms

from apps.accounts.models import Membership, Role
from apps.crm.models import PipelineStage
from apps.integrations.models import LineIntegration
from apps.quotes.models import DocumentNumberSequence

from .models import CompanyProfile


class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = [
            "name_th",
            "name_en",
            "tax_id",
            "branch_kind",
            "branch_code",
            "address",
            "phone",
            "email",
            "website",
            "line_id",
            "logo",
        ]
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in (
            "name_en",
            "tax_id",
            "branch_code",
            "address",
            "phone",
            "email",
            "website",
            "line_id",
            "logo",
        ):
            self.fields[name].required = False


class LineIntegrationForm(forms.ModelForm):
    class Meta:
        model = LineIntegration
        fields = ["channel_id", "channel_secret", "channel_access_token", "is_active"]
        widgets = {"channel_access_token": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False
        # Don't echo a stored access token back in plain text.
        inst = kwargs.get("instance") or getattr(self, "instance", None)
        if inst is not None and inst.pk and inst.channel_access_token:
            self.fields["channel_access_token"].widget.attrs["placeholder"] = (
                "ตั้งค่าแล้ว — กรอกใหม่เพื่อเปลี่ยน"
            )
            if not self.is_bound:
                self.initial["channel_access_token"] = ""

    def clean_channel_access_token(self):
        # Keep the existing token if the field was left blank.
        val = self.cleaned_data.get("channel_access_token", "").strip()
        if not val and self.instance and self.instance.pk:
            return self.instance.channel_access_token
        return val


class PipelineStageForm(forms.ModelForm):
    class Meta:
        model = PipelineStage
        fields = ["name", "kind", "default_probability"]


class DocumentNumberSequenceForm(forms.ModelForm):
    class Meta:
        model = DocumentNumberSequence
        fields = ["doc_type", "year", "last_number"]


class MemberInviteForm(forms.Form):
    email = forms.EmailField(label="อีเมล")
    full_name = forms.CharField(label="ชื่อ-นามสกุล", required=False)
    role = forms.ChoiceField(label="บทบาท", choices=Role.choices, initial=Role.SALES)
    can_see_all_records = forms.BooleanField(label="เห็นข้อมูลของทุกคน", required=False, initial=True)


class MemberRoleForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ["role", "can_see_all_records", "is_active"]
