from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tenants.models import Tenant

from .services import seed_default_pipeline


@receiver(post_save, sender=Tenant, dispatch_uid="crm_seed_default_pipeline")
def seed_pipeline_for_new_tenant(sender, instance: Tenant, created: bool, **kwargs) -> None:
    if created:
        seed_default_pipeline(instance)
