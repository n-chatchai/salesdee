from django.db import migrations

from apps.core.migrations_utils import enable_tenant_rls


class Migration(migrations.Migration):
    dependencies = [
        ("quotes", "0001_initial"),
    ]

    operations = [
        enable_tenant_rls("quotes_documentnumbersequence"),
        enable_tenant_rls("quotes_salesdocument"),
        enable_tenant_rls("quotes_salesdocline"),
    ]
