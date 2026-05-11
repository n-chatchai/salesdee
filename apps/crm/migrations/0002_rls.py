from django.db import migrations

from apps.core.migrations_utils import enable_tenant_rls


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0001_initial"),
    ]

    operations = [
        enable_tenant_rls("crm_customer"),
        enable_tenant_rls("crm_contact"),
        enable_tenant_rls("crm_pipelinestage"),
        enable_tenant_rls("crm_deal"),
        enable_tenant_rls("crm_activity"),
        enable_tenant_rls("crm_task"),
    ]
