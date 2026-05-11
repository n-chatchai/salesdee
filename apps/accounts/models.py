from __future__ import annotations

from typing import ClassVar

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Email-as-login custom user. A user may belong to several tenants via Membership."""

    email = models.EmailField("อีเมล", unique=True)
    full_name = models.CharField("ชื่อ-นามสกุล", max_length=200, blank=True)
    phone = models.CharField("โทรศัพท์", max_length=30, blank=True)
    is_staff = models.BooleanField("เข้า Django admin ได้", default=False)
    is_active = models.BooleanField("เปิดใช้งาน", default=True)
    date_joined = models.DateTimeField("วันที่สมัคร", default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    class Meta:
        verbose_name = "ผู้ใช้"
        verbose_name_plural = "ผู้ใช้"

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        return self.full_name or self.email

    def get_short_name(self) -> str:
        return self.full_name.split(" ", 1)[0] if self.full_name else self.email


class Role(models.TextChoices):
    OWNER = "owner", "เจ้าของ / แอดมิน"
    MANAGER = "manager", "ผู้จัดการ / ผู้อนุมัติ"
    SALES = "sales", "พนักงานขาย"
    ACCOUNTING = "accounting", "บัญชี / การเงิน"
    INSTALLER = "installer", "ช่าง / ทีมติดตั้ง"
    VIEWER = "viewer", "ผู้ดูอย่างเดียว"


class Membership(BaseModel):
    """Links a User to a Tenant with a role + approval caps.

    Not a TenantScopedModel: it *defines* the user↔tenant relationship and is queried
    explicitly by user (middleware) or by tenant (member list).
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    tenant = models.ForeignKey(
        "tenants.Tenant", on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField("บทบาท", max_length=20, choices=Role.choices, default=Role.SALES)
    is_active = models.BooleanField("เปิดใช้งาน", default=True)
    # Used by the discount-approval workflow (REQUIREMENTS.md §4.7 / §4.15).
    max_discount_percent = models.DecimalField(
        "ส่วนลดสูงสุดที่อนุมัติได้ (%)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    approval_limit = models.DecimalField(
        "วงเงินที่อนุมัติได้ (บาท)", max_digits=18, decimal_places=2, null=True, blank=True
    )

    class Meta:
        verbose_name = "สมาชิก Workspace"
        verbose_name_plural = "สมาชิก Workspace"
        constraints = [
            models.UniqueConstraint(fields=["user", "tenant"], name="uniq_membership_user_tenant"),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.tenant} ({self.get_role_display()})"
