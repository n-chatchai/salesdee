from django.db import migrations

from apps.core.migrations_utils import enable_tenant_rls


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0006_salestarget"),
    ]

    operations = [
        enable_tenant_rls("crm_salestarget"),
    ]
