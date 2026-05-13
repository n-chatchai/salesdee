"""Background tasks for slow quotation work (PDF render, email, LINE send) — CLAUDE.md §4.5.

Each task activates the tenant context first, then does the slow bit. Today the configured
backend is ``ImmediateBackend`` so ``.enqueue()`` runs the task synchronously inside the request;
swapping in a durable DB worker / Celery / RQ backend later is a config-only change (no call-site
changes here).
"""

from __future__ import annotations

from django.core.mail import send_mail
from django.tasks import task

from apps.core.current_tenant import tenant_context
from apps.tenants.models import Tenant


def _tenant(tenant_id: int) -> Tenant:
    # Tenant is a global model (BaseModel), so this is safe to fetch with no tenant active.
    return Tenant.objects.get(pk=tenant_id)


@task()
def render_and_email_quotation(
    doc_id: int, tenant_id: int, *, recipient_email: str, recipient_name: str, public_url: str
) -> None:
    """Render the quotation PDF (currently just to confirm it renders / warm caches) and email the
    customer the public link. No-ops gracefully on errors."""
    import contextlib

    with tenant_context(_tenant(tenant_id)):
        from .models import SalesDocument
        from .pdf import render_quotation_pdf

        doc = SalesDocument.objects.filter(pk=doc_id).first()
        if doc is None:
            return
        with contextlib.suppress(Exception):  # best-effort warm-up; the email link is what matters
            render_quotation_pdf(doc)
        if recipient_email:
            send_mail(
                subject=f"ใบเสนอราคา {doc.doc_number}",
                message=(
                    f"เรียนคุณ {recipient_name}\n\nดูใบเสนอราคาได้ที่ลิงก์นี้: {public_url}\n\nขอบคุณครับ"
                ),
                from_email=None,
                recipient_list=[recipient_email],
                fail_silently=True,
            )


@task()
def send_quotation_via_line(
    doc_id: int,
    tenant_id: int,
    *,
    recipient: str,
    doc_number: str,
    customer_name: str,
    total_text: str,
    valid_text: str,
    view_url: str,
    pdf_url: str,
    company_name: str = "",
    log_to_conversation_id: int | None = None,
    sender_user_id: int | None = None,
) -> None:
    """Push the quotation Flex card to ``recipient`` over the tenant's LINE OA; if the quote was
    drafted from a chat, also log the send on that thread. No-ops if LINE isn't configured."""
    with tenant_context(_tenant(tenant_id)):
        from apps.integrations import line as line_mod

        try:
            line_mod.push_quotation_flex(
                recipient,
                doc_number=doc_number,
                customer_name=customer_name,
                total_text=total_text,
                valid_text=valid_text,
                view_url=view_url,
                pdf_url=pdf_url,
                company_name=company_name,
            )
        except Exception:  # noqa: BLE001 — fire-and-forget (incl. LineNotConfigured); don't crash worker
            return
        if log_to_conversation_id is not None:
            from apps.integrations.models import Conversation

            conv = Conversation.objects.filter(pk=log_to_conversation_id).first()
            if conv is not None:
                sender = None
                if sender_user_id is not None:
                    from django.contrib.auth import get_user_model

                    sender = get_user_model().objects.filter(pk=sender_user_id).first()
                line_mod.record_outbound_text(
                    conv, f"ส่งใบเสนอราคา {doc_number} แล้ว", sender_user=sender
                )
