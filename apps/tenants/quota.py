"""Per-tenant per-period quota check + counter increments (Phase B of pricing rollout).

Counters live in `tenants.Usage` (one row per (tenant, period, kind)). Caps live in
`tenants.plans.PLANS[tenant.plan].limits` (config not data). The period is **calendar month
Asia/Bangkok** — `current_period()` returns YYYYMM as an int.

Public API:
- ``current_period() -> int``
- ``check_quota(tenant, kind) -> (ok, used, limit)``
- ``increment_usage(tenant, kind, n=1) -> int`` (new running count)
- ``near_cap(tenant, *, threshold=0.8) -> list[Cap]`` (kinds at ≥ threshold)
- ``QuotaExceeded`` — raised by services that want to hard-block (e.g. tax-invoice issuance)

Counters fail open: any error inside `increment_usage` swallowed (logged) so a quota glitch can
never 500 the LINE webhook or the AI draft path.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import F

from . import plans as plan_registry
from .models import Tenant, Usage

log = logging.getLogger(__name__)

_TZ = ZoneInfo("Asia/Bangkok")


class QuotaExceeded(Exception):
    """A plan's hard-cap for ``kind`` has been hit this period."""

    def __init__(self, kind: str, used: int, limit: int):
        self.kind = kind
        self.used = used
        self.limit = limit
        super().__init__(
            f"แพ็กเกจปัจจุบันใช้ {plan_registry.USAGE_LABELS_TH.get(kind, kind)} "
            f"เต็มเดือนนี้แล้ว ({used}/{limit}) — อัปเกรดเพื่อใช้งานต่อ"
        )


@dataclass(frozen=True)
class Cap:
    kind: str
    label_th: str
    used: int
    limit: int  # -1 = unlimited

    @property
    def is_unlimited(self) -> bool:
        return self.limit == -1

    @property
    def ratio(self) -> float:
        if self.is_unlimited or self.limit == 0:
            return 0.0
        return min(1.0, self.used / self.limit)

    @property
    def pct(self) -> int:
        return int(self.ratio * 100)


def current_period(now: datetime | None = None) -> int:
    """YYYYMM for the calendar month in Asia/Bangkok."""
    if now is None:
        now = datetime.now(_TZ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=_TZ)
    else:
        now = now.astimezone(_TZ)
    return now.year * 100 + now.month


def _plan_for(tenant: Tenant) -> plan_registry.PlanSpec:
    return plan_registry.get(tenant.plan)


def _limit_for(tenant: Tenant, kind: str) -> int:
    return _plan_for(tenant).limits.cap(kind)


def check_quota(tenant: Tenant, kind: str) -> tuple[bool, int, int]:
    """Return ``(ok, used, limit)``. ``limit == -1`` means unlimited (always ok)."""
    if kind not in plan_registry.USAGE_KINDS:
        return True, 0, -1
    limit = _limit_for(tenant, kind)
    row = Usage.all_tenants.filter(tenant=tenant, period=current_period(), kind=kind).first()
    used = row.count if row else 0
    if limit == -1:
        return True, used, -1
    return used < limit, used, limit


def increment_usage(tenant: Tenant, kind: str, n: int = 1) -> int:
    """Atomically bump the counter for the current period. Returns the new running count.

    Best-effort: any DB error is swallowed (we'd rather over-count than break a webhook).
    Returns 0 on failure.
    """
    if kind not in plan_registry.USAGE_KINDS or n <= 0:
        return 0
    period = current_period()
    try:
        with transaction.atomic():
            row, created = Usage.all_tenants.get_or_create(
                tenant=tenant, period=period, kind=kind, defaults={"count": n}
            )
            if not created:
                Usage.all_tenants.filter(pk=row.pk).update(count=F("count") + n)
                row.refresh_from_db(fields=["count"])
        return int(row.count)
    except Exception:  # pragma: no cover - defensive
        log.exception("usage increment failed: tenant=%s kind=%s", tenant.pk, kind)
        return 0


def caps_for_tenant(tenant: Tenant) -> list[Cap]:
    """All `USAGE_KINDS` with their used+limit for the current period — for billing UI."""
    period = current_period()
    rows = {r.kind: r.count for r in Usage.all_tenants.filter(tenant=tenant, period=period)}
    out: list[Cap] = []
    for kind in plan_registry.USAGE_KINDS:
        out.append(
            Cap(
                kind=kind,
                label_th=plan_registry.USAGE_LABELS_TH[kind],
                used=int(rows.get(kind, 0)),
                limit=_limit_for(tenant, kind),
            )
        )
    return out


def near_cap(tenant: Tenant, *, threshold: float = 0.8) -> list[Cap]:
    """Caps at or above ``threshold`` (0..1). Skips unlimited."""
    return [c for c in caps_for_tenant(tenant) if not c.is_unlimited and c.ratio >= threshold]


def enforce_quota(tenant: Tenant, kind: str) -> None:
    """Raise ``QuotaExceeded`` if the tenant is at/over its hard cap for ``kind``."""
    ok, used, limit = check_quota(tenant, kind)
    if not ok:
        raise QuotaExceeded(kind, used, limit)


@contextlib.contextmanager
def gated(tenant: Tenant, kind: str) -> Iterator[None]:
    """Quota-gate a block of work: enforce the cap before the body runs, and on a clean exit
    bump the counter. Raises ``QuotaExceeded`` (caught at the view layer). An exception inside
    the block does NOT increment — we only count successful calls.

    Usage::

        from apps.tenants.quota import gated, QuotaExceeded
        try:
            with gated(request.tenant, "ai_drafts"):
                draft = draft_quotation_from_text(...)
        except QuotaExceeded as e:
            messages.error(request, str(e))
    """
    enforce_quota(tenant, kind)
    yield
    increment_usage(tenant, kind)
