"""Decimal/money helpers. Money is always ``Decimal`` — never ``float`` (CLAUDE.md §4)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# Quantizers: 4dp for stored amounts/line math, 2dp for display/totals on documents.
_MONEY_Q = Decimal("0.0001")
_DISPLAY_Q = Decimal("0.01")
_RATE_Q = Decimal("0.000001")


def D(value: object) -> Decimal:
    """Coerce to Decimal safely (via str, so floats don't introduce binary noise)."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_money(value: object) -> Decimal:
    return D(value).quantize(_MONEY_Q, rounding=ROUND_HALF_UP)


def quantize_display(value: object) -> Decimal:
    return D(value).quantize(_DISPLAY_Q, rounding=ROUND_HALF_UP)


def quantize_rate(value: object) -> Decimal:
    return D(value).quantize(_RATE_Q, rounding=ROUND_HALF_UP)
