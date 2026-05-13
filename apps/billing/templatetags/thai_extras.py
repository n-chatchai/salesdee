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


@register.filter
def get_item(mapping, key):
    """Look up a dict value by a key whose name isn't a valid attr (e.g. ``"1_30"``)."""
    if mapping is None:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        return None
