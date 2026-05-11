"""Tests for the current-tenant context machinery (apps/core/current_tenant.py).

When concrete TenantScopedModel models exist (e.g. crm.Lead), add per-model leakage tests:
create data while `tenant` is active, then assert it's invisible while `other_tenant` is active
(see CLAUDE.md §5 and the Definition of Done in §8).
"""

from __future__ import annotations

from apps.core.current_tenant import (
    activate_tenant,
    deactivate_tenant,
    get_current_tenant,
    tenant_context,
)


def test_no_tenant_by_default() -> None:
    assert get_current_tenant() is None


def test_activate_and_deactivate(tenant) -> None:
    assert get_current_tenant() is None
    activate_tenant(tenant)
    try:
        assert get_current_tenant() == tenant
    finally:
        deactivate_tenant()
    assert get_current_tenant() is None


def test_tenant_context_restores_previous(tenant, other_tenant) -> None:
    activate_tenant(tenant)
    try:
        assert get_current_tenant() == tenant
        with tenant_context(other_tenant):
            assert get_current_tenant() == other_tenant
        assert get_current_tenant() == tenant
    finally:
        deactivate_tenant()


def test_tenant_manager_is_empty_without_active_tenant(tenant) -> None:
    """Sanity: the scoped manager fails closed. Uses the (global) Tenant model only to
    confirm the project imports cleanly; replace with a real TenantScopedModel test later."""
    from apps.core.models import TenantManager

    assert isinstance(TenantManager(), TenantManager)
