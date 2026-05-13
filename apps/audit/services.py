"""Record a tenant-scoped audit event. CLAUDE.md §4 — never silently leak across tenants.

Callers should be inside a tenant context. ``record()`` no-ops if there's no active tenant *and*
no explicit ``tenant`` kwarg (so e.g. failing logins before a workspace is resolved don't crash).
"""

from __future__ import annotations

from typing import Any

from apps.core.current_tenant import get_current_tenant, tenant_context


def record(
    actor=None,
    *,
    action: str,
    obj: Any = None,
    object_type: str = "",
    object_id: int | None = None,
    object_repr: str = "",
    changes: dict | None = None,
    ip: str | None = None,
    tenant=None,
):
    """Create an ``AuditEvent`` row. Returns the row, or None if we have no tenant to attribute it
    to (best-effort — auditing should never break the caller)."""
    from .models import AuditEvent

    active = tenant or get_current_tenant()
    if active is None:
        return None
    if obj is not None:
        object_type = object_type or obj.__class__.__name__
        object_id = object_id if object_id is not None else getattr(obj, "pk", None)
        object_repr = object_repr or str(obj)[:255]
    actor_user = (
        actor if (actor is not None and getattr(actor, "is_authenticated", False)) else None
    )
    with tenant_context(active):
        return AuditEvent.objects.create(
            actor=actor_user,
            action=action,
            object_type=object_type[:80],
            object_id=object_id,
            object_repr=object_repr[:255],
            changes=changes or {},
            ip=ip,
        )
