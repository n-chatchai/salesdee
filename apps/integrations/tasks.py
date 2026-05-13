"""Background tasks for LINE integration (profile-name enrichment, …) — CLAUDE.md §4.5.

The configured task backend is ``ImmediateBackend`` today (runs synchronously inside
``.enqueue()``); a durable worker / Celery / RQ backend is a config-only swap later.
Everything here is best-effort: if LINE isn't configured or the API errors, the task no-ops
rather than crashing (the webhook must never 500 because of this).
"""

from __future__ import annotations

from apps.core.current_tenant import tenant_context
from apps.core.tasks import task
from apps.tenants.models import Tenant


@task()
def enrich_conversation_display_name(conversation_id: int, tenant_id: int) -> None:
    """Look up the LINE profile for the conversation's user and set ``display_name`` (and the
    linked lead's name if it's still the auto ``"ลูกค้า LINE ……"`` placeholder)."""
    with tenant_context(Tenant.objects.get(pk=tenant_id)):
        from .line import fetch_line_profile_name
        from .models import Conversation

        conv = Conversation.objects.filter(pk=conversation_id).select_related("lead").first()
        if conv is None or not conv.external_id:
            return
        name = fetch_line_profile_name(conv.external_id)
        if not name:
            return
        if conv.display_name != name:
            conv.display_name = name
            conv.save(update_fields=["display_name"])
        lead = conv.lead
        if lead is not None and lead.name.startswith("ลูกค้า LINE "):
            lead.name = name
            lead.save(update_fields=["name"])
