from django.db import migrations

from apps.core.migrations_utils import enable_tenant_rls


class Migration(migrations.Migration):
    dependencies = [
        ("quotes", "0005_salesdocument_revision_note_quotationrevision"),
    ]

    operations = [
        enable_tenant_rls("quotes_quotationrevision"),
    ]
