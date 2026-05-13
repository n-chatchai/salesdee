from django.db import migrations

from apps.core.migrations_utils import enable_tenant_rls


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0003_conversation_message_and_more"),
    ]

    operations = [
        enable_tenant_rls("integrations_conversation"),
        enable_tenant_rls("integrations_message"),
    ]
