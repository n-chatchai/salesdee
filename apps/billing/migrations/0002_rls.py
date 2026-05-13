from django.db import migrations

from apps.core.migrations_utils import enable_tenant_rls


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        enable_tenant_rls("billing_payment"),
        enable_tenant_rls("billing_paymentallocation"),
    ]
