"""Furniture-aware product catalog.  Spec: REQUIREMENTS.md §4.6.

To build (phase 1):
  - ProductCategory (multi-level)
  - Product (code, name, description, images, unit, default price, cost?, tax type, standard, tags)
  - ProductAttribute / structured fields (W×D×H, material, finish, color code, hardware brand)
  - ProductVariant (size/color/material variants, own price/cost/sku)
  - ProductOption (per-product add-ons with extra price)
  - BundleItem (a bundle product composed of component products/variants)
  - Excel import/export

Tenant-owned → inherit ``apps.core.models.TenantScopedModel``.
"""

from apps.core.models import TenantScopedModel  # noqa: F401
