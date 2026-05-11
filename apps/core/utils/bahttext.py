"""Convert a monetary amount to Thai words (BahtText).

It's on every document — keep the tests in apps/core/tests/test_bahttext.py green and
add cases when you find an edge case.

Examples:
    baht_text("0")          -> "ศูนย์บาทถ้วน"
    baht_text("100")        -> "หนึ่งร้อยบาทถ้วน"
    baht_text("21")         -> "ยี่สิบเอ็ดบาทถ้วน"
    baht_text("1234567.89") -> "หนึ่งล้านสองแสนสามหมื่นสี่พันห้าร้อยหกสิบเจ็ดบาทแปดสิบเก้าสตางค์"
    baht_text("0.50")       -> "ห้าสิบสตางค์"
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

_DIGITS = ["ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
_PLACES = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]  # positions 0..5 within a 6-digit group


def _read_below_million(n: int) -> str:
    """Read 0 <= n < 1_000_000. Returns '' for 0."""
    if n == 0:
        return ""
    digits = str(n)
    length = len(digits)
    out: list[str] = []
    for i, ch in enumerate(digits):
        d = int(ch)
        if d == 0:
            continue
        pos = length - i - 1  # 0 = units, 1 = tens, ...
        if pos == 0 and d == 1 and length > 1:
            out.append("เอ็ด")
        elif pos == 1 and d == 1:
            out.append("สิบ")
        elif pos == 1 and d == 2:
            out.append("ยี่สิบ")
        else:
            out.append(_DIGITS[d] + _PLACES[pos])
    return "".join(out)


def _read_int(n: int) -> str:
    if n == 0:
        return "ศูนย์"
    if n < 1_000_000:
        return _read_below_million(n)
    millions, remainder = divmod(n, 1_000_000)
    text = _read_int(millions) + "ล้าน"
    if remainder:
        # "เอ็ด" applies because the whole number has more than one digit.
        text += "เอ็ด" if remainder == 1 else _read_below_million(remainder)
    return text


def baht_text(amount: object) -> str:
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "ลบ" if value < 0 else ""
    value = abs(value)
    baht = int(value)
    satang = int((value - baht) * 100)

    if baht == 0 and satang == 0:
        return "ศูนย์บาทถ้วน"

    parts: list[str] = [sign]
    if baht > 0:
        parts.append(_read_int(baht) + "บาท")
    if satang == 0:
        parts.append("ถ้วน")
    else:
        parts.append(_read_below_million(satang) + "สตางค์")
    return "".join(p for p in parts if p)
