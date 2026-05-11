"""PHASE 3 — basic accounting.  Spec: REQUIREMENTS.md §4.14.2–§4.14.6.

Scope: Thai chart of accounts (customisable), account mapping, auto-posting from sales/payment
documents, journal entries (incl. manual JV), general ledger, trial balance, accounting periods
(open/closed/locked), opening balances, basic P&L / Balance Sheet, accounting dimensions
(dept/project/cost-center).

NOT in scope even here: purchase cycle / AP, inventory & costing, fixed assets & depreciation,
cash-flow statement, e-filed ภ.พ.30 / ภ.ง.ด., consolidation.

Empty for now — do not build until phase 2.
"""

from apps.core.models import BaseModel, TenantScopedModel  # noqa: F401
