"""Single source of truth for "is feature X enabled for tenant Y?".

Resolution order (first match wins):
1. ``settings.PLATFORM_DISABLED_MODULES`` — platform-wide kill switch (incident handling)
2. Active ``TenantFeatureOverride`` row → use its mode (FORCE_ON / FORCE_OFF)
3. Otherwise fall back to the tenant's plan defaults (apps/tenants/plans.py)

Module codes accepted (must match ``apps/tenants/modules.py``):
- billing · e_tax · white_label · custom_domain · api · priority_support · sla

Callers:
- BillingFeatureGateMiddleware (middleware.py) — gates /billing/* by ``billing``
- context_processors.plan_has_billing — hides sidebar by ``billing``
- modules.get_modules — drives the read-only status page
"""

from __future__ import annotations

from datetime import date

from django.conf import settings

from . import plans as plan_registry
from .models import FeatureOverrideMode, TenantFeatureOverride


def is_platform_disabled(code: str) -> bool:
    """``True`` if this module is kill-switched at the platform level."""
    return code in getattr(settings, "PLATFORM_DISABLED_MODULES", [])


def _from_plan(tenant, code: str) -> bool:
    f = plan_registry.get(tenant.plan).features
    if code == "billing":
        return f.billing_module
    if code == "e_tax":
        return f.e_tax_invoice
    if code == "white_label":
        return f.white_label_pdf
    if code == "custom_domain":
        return f.custom_domain
    if code == "api":
        return f.api_access != "none"
    if code == "priority_support":
        return f.priority_support
    if code == "sla":
        return f.sla
    return False


def _override(tenant, code: str) -> TenantFeatureOverride | None:
    """Return the active override row for this (tenant, code), or None."""
    today = date.today()
    return (
        TenantFeatureOverride.objects.filter(tenant=tenant, module_code=code)
        .filter(models_Q_active(today))
        .first()
    )


def models_Q_active(today):
    """Q-expression: expires_at IS NULL OR expires_at >= today."""
    from django.db.models import Q

    return Q(expires_at__isnull=True) | Q(expires_at__gte=today)


def feature_enabled(tenant, code: str) -> bool:
    """``True`` if the tenant should currently have access to this feature.

    Platform kill switch wins over everything; then override; then plan defaults.
    """
    if tenant is None:
        return False
    if is_platform_disabled(code):
        return False
    ov = _override(tenant, code)
    if ov is not None:
        return ov.mode == FeatureOverrideMode.FORCE_ON
    return _from_plan(tenant, code)


def get_override(tenant, code: str) -> TenantFeatureOverride | None:
    """Public re-export for callers that need to surface the override (e.g. the modules page)."""
    return _override(tenant, code)
