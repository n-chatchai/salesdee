"""The 'current tenant' context for the running request/task.

Read CLAUDE.md §5 before touching this. Every tenant-scoped query is filtered by
whatever tenant is active here. The request middleware (apps.core.middleware) sets
it for web requests; background tasks / scripts / public token views must set it
themselves via ``tenant_context()``.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from apps.tenants.models import Tenant

_current_tenant: ContextVar[Tenant | None] = ContextVar("current_tenant", default=None)


def get_current_tenant() -> Tenant | None:
    return _current_tenant.get()


def activate_tenant(tenant: Tenant) -> None:
    _current_tenant.set(tenant)
    _sync_db_session_var(tenant.pk)


def deactivate_tenant() -> None:
    _current_tenant.set(None)
    _sync_db_session_var(None)


@contextmanager
def tenant_context(tenant: Tenant | None) -> Iterator[None]:
    """Run a block of code as a given tenant (or with no tenant). Restores the
    previous tenant on exit. Use in Celery/django.tasks tasks, management commands,
    and the public quote-view (token-resolved) flow.
    """
    token = _current_tenant.set(tenant)
    _sync_db_session_var(tenant.pk if tenant is not None else None)
    try:
        yield
    finally:
        _current_tenant.reset(token)
        prev = _current_tenant.get()
        _sync_db_session_var(prev.pk if prev is not None else None)


def _sync_db_session_var(tenant_id: object) -> None:
    """Mirror the active tenant into a Postgres session variable for RLS policies.

    No-op unless ``settings.RLS_ENABLED`` is True (RLS policies are added in a later
    migration). App-layer manager scoping is always in effect regardless.
    """
    from django.conf import settings

    if not getattr(settings, "RLS_ENABLED", False):
        return
    from django.db import connection

    value = str(tenant_id) if tenant_id else ""
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.current_tenant_id', %s, false)", [value])
