from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify

from apps.tenants.models import Tenant


class SignupForm(forms.Form):
    workspace_name = forms.CharField(label="ชื่อธุรกิจ / Workspace", max_length=200)
    slug = forms.SlugField(
        label="ชื่อพื้นที่ทำงาน (URL)",
        max_length=63,
        help_text="ใช้เป็นที่อยู่: <ชื่อนี้>.salesdee.app",
    )
    full_name = forms.CharField(label="ชื่อ-นามสกุล", max_length=200)
    email = forms.EmailField(label="อีเมล")
    password = forms.CharField(label="รหัสผ่าน", widget=forms.PasswordInput)

    def clean_slug(self):
        slug = slugify(self.cleaned_data["slug"])
        if not slug:
            raise forms.ValidationError("กรุณาระบุชื่อพื้นที่ทำงานที่ถูกต้อง")
        if Tenant.objects.filter(slug=slug).exists():
            raise forms.ValidationError("ชื่อพื้นที่ทำงานนี้ถูกใช้แล้ว ลองชื่ออื่น")
        return slug

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if get_user_model().objects.filter(email=email).exists():
            raise forms.ValidationError("อีเมลนี้มีบัญชีอยู่แล้ว")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password
