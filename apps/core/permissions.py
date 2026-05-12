"""Role / record-visibility helpers (REQUIREMENTS.md §4.15).

Two jobs:
  * gate manager-only pages (``is_manager`` / ``can_view_reports``), and
  * scope list/detail querysets to records the current user owns when their membership has
    ``can_see_all_records`` turned off (``own_q``).

All take the request — the active tenant comes from ``request.tenant`` (set by CurrentTenantMiddleware).
"""

from __future__ import annotations

from django.db.models import Q


def _tenant_id(request) -> object | None:
    tenant = getattr(request, "tenant", None)
    return tenant.pk if tenant is not None else None


def membership_of(request):
    """The requesting user's active Membership for the current tenant, or None."""
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    tenant_id = _tenant_id(request)
    if tenant_id is None:
        return None
    from apps.accounts.models import Membership

    return Membership.objects.filter(user=user, tenant_id=tenant_id, is_active=True).first()


def is_manager(request) -> bool:
    """Owner / manager — may approve discounts and see across the workspace by default."""
    from apps.accounts.models import Role

    m = membership_of(request)
    return m is not None and m.role in (Role.OWNER, Role.MANAGER)


def can_view_reports(request) -> bool:
    """Reports are for owners, managers and accounting."""
    from apps.accounts.models import Role

    m = membership_of(request)
    return m is not None and m.role in (Role.OWNER, Role.MANAGER, Role.ACCOUNTING)


def restricted_to_own(request) -> bool:
    """True if this user should only see records they own (membership.can_see_all_records is off)."""
    m = membership_of(request)
    return m is not None and not m.can_see_all_records


def own_q(request, owner_field: str) -> Q:
    """An empty ``Q`` if the user sees everything, otherwise ``Q(<owner_field>=request.user)`` —
    AND this onto a queryset to limit it to the user's own records."""
    if not restricted_to_own(request):
        return Q()
    return Q(**{owner_field: request.user})
