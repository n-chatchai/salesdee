from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tenants.models import CompanyProfile, Tenant

from .services import seed_default_pipeline


@receiver(post_save, sender=Tenant, dispatch_uid="crm_provision_new_tenant")
def provision_new_tenant(sender, instance: Tenant, created: bool, **kwargs) -> None:
    if not created:
        return
    seed_default_pipeline(instance)
    CompanyProfile.objects.get_or_create(tenant=instance, defaults={"name_th": instance.name})
