"""Thai date helpers. Documents default to Buddhist Era (พ.ศ.) — see settings.DOCUMENT_ERA."""

from __future__ import annotations

import datetime as _dt

from django.conf import settings

THAI_MONTHS = [
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
]
THAI_MONTHS_ABBR = [
    "ม.ค.",
    "ก.พ.",
    "มี.ค.",
    "เม.ย.",
    "พ.ค.",
    "มิ.ย.",
    "ก.ค.",
    "ส.ค.",
    "ก.ย.",
    "ต.ค.",
    "พ.ย.",
    "ธ.ค.",
]

BE_OFFSET = 543


def to_be_year(year: int) -> int:
    return year + BE_OFFSET


def from_be_year(be_year: int) -> int:
    return be_year - BE_OFFSET


def format_thai_date(d: _dt.date, *, era: str | None = None, abbr: bool = False) -> str:
    """e.g. format_thai_date(date(2026, 5, 11)) -> '11 พฤษภาคม 2569'."""
    era = era or getattr(settings, "DOCUMENT_ERA", "BE")
    year = to_be_year(d.year) if era == "BE" else d.year
    months = THAI_MONTHS_ABBR if abbr else THAI_MONTHS
    return f"{d.day} {months[d.month - 1]} {year}"
