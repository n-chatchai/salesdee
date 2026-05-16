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


class OnboardingDomainForm(forms.Form):
    """Step 2 of onboarding: pick a subdomain (Tenant.slug) + upload a logo."""

    slug = forms.SlugField(
        label="Subdomain",
        max_length=63,
        help_text="ที่อยู่ที่ลูกค้าใช้: <slug>.salesdee.app",
    )
    logo = forms.ImageField(label="โลโก้", required=False)

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant is not None and not self.is_bound:
            self.fields["slug"].initial = tenant.slug

    def clean_slug(self):
        from django.utils.text import slugify

        from apps.tenants.models import Tenant

        slug = slugify(self.cleaned_data["slug"])
        if not slug:
            raise forms.ValidationError("กรุณาระบุ subdomain ที่ถูกต้อง")
        qs = Tenant.objects.filter(slug=slug)
        if self.tenant is not None:
            qs = qs.exclude(pk=self.tenant.pk)
        if qs.exists():
            raise forms.ValidationError("subdomain นี้ถูกใช้แล้ว ลองชื่ออื่น")
        return slug


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
