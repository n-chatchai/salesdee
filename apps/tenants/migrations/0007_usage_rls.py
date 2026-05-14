from django.db import migrations

from apps.core.migrations_utils import enable_tenant_rls


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0006_usage"),
    ]

    operations = [
        enable_tenant_rls("tenants_usage"),
    ]
