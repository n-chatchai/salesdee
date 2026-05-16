from django.db import migrations

from apps.core.migrations_utils import enable_tenant_rls


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_public_site_fields"),
    ]

    operations = [
        enable_tenant_rls("catalog_portfoliocase"),
    ]
