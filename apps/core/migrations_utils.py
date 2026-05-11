"""Helpers for migrations — notably enabling Postgres Row-Level Security on tenant tables.

Read CLAUDE.md §5. Every table with a ``tenant_id`` column should get an RLS policy via
``enable_tenant_rls()`` in its app's migrations (a separate migration that depends on the
``CreateModel`` migration is the cleanest).

Enforcement note: RLS is bypassed by the table OWNER and by superusers unless ``FORCE ROW
LEVEL SECURITY`` is set. We do **not** force it here, so in single-role dev/CI (where the
app connects as the table owner) RLS is effectively a no-op and the app-layer ``TenantManager``
is what isolates tenants. In production, run the app as a **non-owner, non-superuser** role and
set ``RLS_ENABLED=true`` so the per-request ``app.current_tenant_id`` session var is set — then
RLS becomes the real backstop. (Or add ``FORCE`` here once you've split the roles.)
"""

from __future__ import annotations

from django.db import migrations

_POLICY_NAME = "tenant_isolation"


def enable_tenant_rls(
    table: str,
    *,
    tenant_column: str = "tenant_id",
    id_cast: str = "bigint",
) -> migrations.RunSQL:
    """Return a RunSQL operation that enables RLS on ``table`` and creates a policy
    restricting visibility/writes to rows of the tenant in ``current_setting('app.current_tenant_id')``.

    Fails closed: if the session var is unset or empty, ``NULLIF(...)::cast`` is NULL, so the
    ``tenant_column = NULL`` comparison is NULL → no rows visible / insertable.
    """
    expr = (
        f"{tenant_column} = NULLIF(current_setting('app.current_tenant_id', true), '')::{id_cast}"
    )
    forward = [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;",
        f"CREATE POLICY {_POLICY_NAME} ON {table} USING ({expr}) WITH CHECK ({expr});",
    ]
    reverse = [
        f"DROP POLICY IF EXISTS {_POLICY_NAME} ON {table};",
        f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;",
    ]
    # django-stubs types RunSQL's sql params as an invariant list; a plain list[str] is fine at runtime.
    return migrations.RunSQL(sql=forward, reverse_sql=reverse)  # type: ignore[arg-type]
