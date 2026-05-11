from django.db import migrations

from apps.core.migrations_utils import enable_tenant_rls


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        enable_tenant_rls("catalog_productcategory"),
        enable_tenant_rls("catalog_product"),
        enable_tenant_rls("catalog_productimage"),
        enable_tenant_rls("catalog_productvariant"),
        enable_tenant_rls("catalog_productoption"),
        enable_tenant_rls("catalog_bundleitem"),
    ]
