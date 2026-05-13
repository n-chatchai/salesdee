"""Template helpers for documents — Buddhist-Era date formatting (CLAUDE.md §7)."""

from __future__ import annotations

from django import template

from apps.core.utils.thai_dates import format_thai_date

register = template.Library()


@register.filter
def thai_date(value):
    if not value:
        return "-"
    return format_thai_date(value, abbr=True)
