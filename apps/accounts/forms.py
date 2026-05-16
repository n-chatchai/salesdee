from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify

from apps.tenants.models import Tenant


class SignupForm(forms.Form):
    full_name = forms.CharField(label="ชื่อ-นามสกุล", max_length=200)
    email = forms.EmailField(label="อีเมลธุรกิจ")
    password = forms.CharField(label="รหัสผ่าน", widget=forms.PasswordInput, min_length=8)
    workspace_name = forms.CharField(label="ชื่อบริษัท", max_length=200)
    phone = forms.CharField(label="เบอร์โทร", max_length=40, required=False)

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if get_user_model().objects.filter(email=email).exists():
            raise forms.ValidationError("อีเมลนี้มีบัญชีอยู่แล้ว")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        workspace_name = cleaned.get("workspace_name")
        if not workspace_name:
            return cleaned
        base_slug = slugify(workspace_name) or "workspace"
        slug = base_slug
        counter = 2
        while Tenant.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        cleaned["slug"] = slug
        return cleaned
