from django.db import migrations

from apps.core.migrations_utils import enable_tenant_rls


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0002_bankaccount_companyprofile"),
    ]

    operations = [
        enable_tenant_rls("tenants_companyprofile"),
        enable_tenant_rls("tenants_bankaccount"),
    ]
