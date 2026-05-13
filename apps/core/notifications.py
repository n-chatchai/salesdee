"""Email / LINE notifications — daily digest, quote-viewed pings, AR-due reminders (PRD §05, FR-13.5).

Each task activates the tenant context first (CLAUDE.md §5), builds its content, and sends best-effort
(``fail_silently=True`` / swallow LINE errors). The configured task backend is ``ImmediateBackend``
today; swapping in a durable worker is config-only.
"""

from __future__ import annotations

from types import SimpleNamespace

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.tasks import task
from django.template.loader import render_to_string

from apps.core.current_tenant import tenant_context
from apps.tenants.models import Tenant


def _tenant(tenant_id: int) -> Tenant | None:
    # Tenant is a global model (BaseModel) — safe to fetch with no tenant active.
    return Tenant.objects.filter(pk=tenant_id).first()


def _fake_request(user, tenant):
    """A minimal stand-in for an HttpRequest that ``build_dashboard`` / ``build_notifications`` /
    ``own_q`` need (they only read ``.user`` and ``.tenant``)."""
    return SimpleNamespace(user=user, tenant=tenant)


@task()
def send_daily_digest(tenant_id: int, user_id: int) -> None:
    """Email one workspace member their daily feed (overdue tasks, awaiting quotes, new leads, …)."""
    from django.contrib.auth import get_user_model

    tenant = _tenant(tenant_id)
    if tenant is None or not tenant.is_active:
        return
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None or not user.email:
        return
    with tenant_context(tenant):
        from apps.accounts.models import Membership
        from apps.crm.dashboard import build_notifications

        if not Membership.objects.filter(user=user, tenant=tenant, is_active=True).exists():
            return
        req = _fake_request(user, tenant)
        items = build_notifications(req)
        if not items:
            return  # nothing to nag about today
        ctx = {
            "user": user,
            "tenant": tenant,
            "items": items[:30],
            "count": len(items),
        }
        subject = f"[{tenant.name}] สรุปงานวันนี้ ({len(items)} รายการ)"
        text_body = render_to_string("email/daily_digest.txt", ctx)
        html_body = render_to_string("email/daily_digest.html", ctx)
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=True)


@task()
def notify_quote_viewed(document_id: int, tenant_id: int) -> None:
    """Tell a quotation's salesperson the customer just opened the share link for the first time."""
    tenant = _tenant(tenant_id)
    if tenant is None:
        return
    with tenant_context(tenant):
        from apps.quotes.models import SalesDocument

        doc = (
            SalesDocument.objects.filter(pk=document_id)
            .select_related("salesperson", "customer")
            .first()
        )
        if doc is None or doc.salesperson is None or not doc.salesperson.email:
            return
        customer = doc.customer.name if doc.customer else ""
        send_mail(
            subject=f"ลูกค้าเปิดดูใบเสนอราคา {doc.doc_number} แล้ว",
            message=(
                f"เรียนคุณ {doc.salesperson.get_full_name() or doc.salesperson.email}\n\n"
                f"ลูกค้า {customer} เพิ่งเปิดดูใบเสนอราคา {doc.doc_number} เป็นครั้งแรก "
                f"อาจเป็นจังหวะดีที่จะติดตามผล\n\nระบบ salesdee"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[doc.salesperson.email],
            fail_silently=True,
        )


@task()
def send_ar_reminder(invoice_id: int, tenant_id: int) -> None:
    """Email the salesperson + customer contact a payment reminder for an overdue/near-due invoice;
    also LINE-text the contact a short note if they have a LINE id and LINE is configured."""
    from decimal import Decimal

    tenant = _tenant(tenant_id)
    if tenant is None:
        return
    with tenant_context(tenant):
        from apps.billing.services import invoice_outstanding
        from apps.quotes.models import SalesDocument

        inv = (
            SalesDocument.objects.filter(pk=invoice_id)
            .select_related("salesperson", "customer", "contact")
            .first()
        )
        if inv is None:
            return
        outstanding = invoice_outstanding(inv)
        if outstanding <= Decimal("0"):
            return
        recipients = []
        if inv.salesperson and inv.salesperson.email:
            recipients.append(inv.salesperson.email)
        if inv.contact and inv.contact.email:
            recipients.append(inv.contact.email)
        customer = inv.customer.name if inv.customer else ""
        due = inv.due_date.isoformat() if inv.due_date else "-"
        body = (
            f"แจ้งเตือนยอดค้างชำระ\n\n"
            f"ลูกค้า: {customer}\n"
            f"เอกสาร: {inv.doc_number}\n"
            f"ครบกำหนด: {due}\n"
            f"ยอดค้างชำระ: {outstanding:,.2f} บาท\n\n"
            f"ระบบ salesdee"
        )
        if recipients:
            send_mail(
                subject=f"แจ้งเตือนยอดค้างชำระ {inv.doc_number}",
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=True,
            )
        if inv.contact and inv.contact.line_id:
            import contextlib

            from apps.integrations import line as line_mod

            if line_mod.line_is_configured():
                with contextlib.suppress(Exception):  # best-effort
                    line_mod.push_text(
                        inv.contact.line_id,
                        f"แจ้งเตือน: ใบแจ้งหนี้ {inv.doc_number} ยอดค้างชำระ "
                        f"{outstanding:,.2f} บาท ครบกำหนด {due}",
                    )


@task()
def notify_new_lead(lead_id: int, tenant_id: int) -> None:
    """Tell the workspace's owners/managers a new lead just came in from the public intake form.
    Best-effort email to every active manager/owner; the LINE notify is via the contact's LINE
    later if they replied. No-ops if no recipients."""
    import contextlib

    tenant = _tenant(tenant_id)
    if tenant is None:
        return
    with tenant_context(tenant):
        from apps.accounts.models import Membership, Role
        from apps.crm.models import Lead

        lead = Lead.objects.filter(pk=lead_id).first()
        if lead is None:
            return
        recipients = list(
            Membership.objects.filter(
                tenant=tenant, is_active=True, role__in=(Role.OWNER, Role.MANAGER)
            )
            .select_related("user")
            .values_list("user__email", flat=True)
        )
        recipients = [e for e in recipients if e]
        if recipients:
            interest = lead.product_interest or "ไม่ระบุ"
            body = (
                f"มีลีดใหม่จากหน้าโชว์รูม\n\n"
                f"ชื่อ: {lead.name}\n"
                f"สนใจ: {interest}\n"
                f"โทร: {lead.phone or '—'}\n"
                f"อีเมล: {lead.email or '—'}\n"
                f"LINE: {lead.line_id or '—'}\n"
                f"งบประมาณ: {lead.budget or '—'}\n\n"
                f"ข้อความ:\n{lead.message or '—'}\n\n"
                f"ระบบ salesdee"
            )
            with contextlib.suppress(Exception):
                send_mail(
                    subject=f"ลีดใหม่ · {lead.name} (สนใจ {interest})",
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=recipients,
                    fail_silently=True,
                )
