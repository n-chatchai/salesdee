"""External integrations.  Spec: REQUIREMENTS.md §4.16.

Phase 1: LINE Official Account (receive/send messages, send documents, customer notifications) +
email (in/out). Stores per-tenant LINE channel credentials (encrypted) and a unified Message log.
Phase 3: public REST API / webhooks; export/sync to accounting software (FlowAccount/PEAK/Express).

Tenant-owned config (e.g. LineIntegration) → ``TenantScopedModel``.
"""

from apps.core.models import TenantScopedModel  # noqa: F401
