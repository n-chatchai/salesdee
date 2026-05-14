from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.current_tenant import tenant_context
from apps.tenants.models import Tenant

from .line import LineNotConfigured, process_line_events, push_text, record_outbound_text
from .models import Conversation, ConversationStatus, LineIntegration

# --- Unified inbox -----------------------------------------------------------
_INBOX_FILTERS = ("open", "mine", "unassigned", "all")


def _conversations_qs(request: HttpRequest, *, scope: str):
    assert request.user.is_authenticated  # @login_required guarantees this; narrows the type
    qs = Conversation.objects.select_related("customer", "lead", "assigned_to")
    if scope == "open":
        qs = qs.filter(status=ConversationStatus.OPEN)
    elif scope == "mine":
        qs = qs.filter(assigned_to=request.user)
    elif scope == "unassigned":
        qs = qs.filter(assigned_to__isnull=True, status=ConversationStatus.OPEN)
    return qs


@login_required
def inbox(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    """Unified inbox: thread list + (optionally) the selected conversation transcript + AI rail."""
    scope = request.GET.get("scope", "open")
    if scope not in _INBOX_FILTERS:
        scope = "open"
    conversations = list(_conversations_qs(request, scope=scope)[:200])
    selected = None
    if pk is not None:
        selected = get_object_or_404(
            Conversation.objects.select_related("customer", "lead", "assigned_to"), pk=pk
        )
        _mark_read(selected)
    ctx = {
        "conversations": conversations,
        "scope": scope,
        "selected": selected,
        "messages_qs": selected.messages.all() if selected else None,
    }
    if request.headers.get("HX-Request") and request.GET.get("partial") == "list":
        return render(request, "integrations/_thread_list.html", ctx)
    return render(request, "integrations/inbox.html", ctx)


def _mark_read(conv: Conversation) -> None:
    if conv.unread_count:
        conv.unread_count = 0
        conv.save(update_fields=["unread_count"])


def _conversation_partial(request: HttpRequest, conv: Conversation, **extra) -> HttpResponse:
    ctx = {"selected": conv, "messages_qs": conv.messages.all(), **extra}
    return render(request, "integrations/_conversation.html", ctx)


@login_required
@require_POST
def conversation_reply(request: HttpRequest, pk: int) -> HttpResponse:
    conv = get_object_or_404(Conversation, pk=pk)
    text = (request.POST.get("text") or "").strip()
    if not text:
        return _conversation_partial(request, conv, error="พิมพ์ข้อความก่อนส่ง")
    try:
        push_text(conv.external_id, text)
    except LineNotConfigured:
        return _conversation_partial(request, conv, error="ยังไม่ได้ตั้งค่าการเชื่อม LINE OA")
    except Exception:  # SDK/network error
        return _conversation_partial(request, conv, error="ส่งข้อความไม่สำเร็จ ลองใหม่อีกครั้ง")
    record_outbound_text(conv, text, sender_user=request.user)
    conv.refresh_from_db()
    return _conversation_partial(request, conv)


@login_required
@require_POST
def conversation_assign(request: HttpRequest, pk: int) -> HttpResponse:
    assert request.user.is_authenticated  # @login_required guarantees this; narrows the type
    conv = get_object_or_404(Conversation, pk=pk)
    conv.assigned_to = None if request.POST.get("unassign") else request.user
    conv.save(update_fields=["assigned_to"])
    return _conversation_partial(request, conv)


@login_required
@require_POST
def conversation_status(request: HttpRequest, pk: int) -> HttpResponse:
    conv = get_object_or_404(Conversation, pk=pk)
    new_status = request.POST.get("status")
    if new_status in ConversationStatus.values:
        conv.status = new_status
        conv.save(update_fields=["status"])
    return _conversation_partial(request, conv)


@login_required
@require_POST
def conversation_ai_reply(request: HttpRequest, pk: int) -> HttpResponse:
    """Draft 1-3 reply suggestions for this conversation using the AI helper (sage UI)."""
    from .ai import AINotConfigured, ai_is_configured, draft_reply_from_text

    conv = get_object_or_404(Conversation, pk=pk)
    suggestions: list[str] = []
    error = ""
    if not ai_is_configured():
        error = "ยังไม่ได้ตั้งค่าผู้ช่วย AI"
    else:
        transcript = "\n".join(
            f"{'ลูกค้า' if m.direction == 'in' else 'เรา'}: {m.text}"
            for m in conv.messages.all()
            if m.text
        )
        company = ""
        try:
            from apps.tenants.models import CompanyProfile

            profile = CompanyProfile.objects.filter(tenant_id=conv.tenant_id).first()
            company = profile.name_th if profile else ""
        except Exception:
            pass
        from apps.tenants.quota import QuotaExceeded, gated

        try:
            with gated(conv.tenant, "ai_drafts"):
                reply = draft_reply_from_text(transcript, company_name=company)
            if reply:
                suggestions = [reply]
        except QuotaExceeded as exc:
            error = str(exc)
        except AINotConfigured:
            error = "ยังไม่ได้ตั้งค่าผู้ช่วย AI"
        except Exception:
            error = "ผู้ช่วยตอบไม่สำเร็จ ลองใหม่อีกครั้ง"
    return render(
        request,
        "integrations/_ai_suggestions.html",
        {"selected": conv, "suggestions": suggestions, "error": error},
    )


@login_required
@require_POST
def conversation_ai_summary(request: HttpRequest, pk: int) -> HttpResponse:
    """Draft a short Thai summary of the customer/their needs/where the deal stands (sage UI)."""
    from .ai import AINotConfigured, ai_is_configured, summarize_conversation

    conv = get_object_or_404(Conversation.objects.select_related("customer", "lead"), pk=pk)
    summary = ""
    error = ""
    if not ai_is_configured():
        error = "ยังไม่ได้ตั้งค่าผู้ช่วย AI"
    else:
        transcript = "\n".join(
            f"{'ลูกค้า' if m.direction == 'in' else 'เรา'}: {m.text}"
            for m in conv.messages.all()
            if m.text
        )
        if not transcript:
            error = "บทสนทนานี้ยังไม่มีข้อความให้สรุป"
        else:
            name = conv.display_name or (
                conv.customer.name if conv.customer else (conv.lead.name if conv.lead else "")
            )
            from apps.tenants.quota import QuotaExceeded, gated

            try:
                with gated(conv.tenant, "ai_drafts"):
                    summary = summarize_conversation(transcript, customer_name=name)
            except QuotaExceeded as exc:
                error = str(exc)
            except AINotConfigured:
                error = "ยังไม่ได้ตั้งค่าผู้ช่วย AI"
            except Exception:
                error = "ผู้ช่วยสรุปไม่สำเร็จ ลองใหม่อีกครั้ง"
    return render(
        request,
        "integrations/_ai_summary.html",
        {"selected": conv, "summary": summary, "error": error},
    )


@login_required
@require_POST
def conversation_make_quote(request: HttpRequest, pk: int) -> HttpResponse:
    """Quote-from-Chat: draft a quotation from this conversation's transcript (Claude), link it to
    the thread, and open the editor for the salesperson to review before sending."""
    from django.contrib import messages

    from apps.catalog.models import Product
    from apps.quotes.services import create_quotation_from_ai_draft

    from .ai import AINotConfigured, draft_quotation_from_text

    conv = get_object_or_404(Conversation.objects.select_related("customer", "lead"), pk=pk)
    transcript = "\n".join(
        f"{'ลูกค้า' if m.direction == 'in' else 'เรา'}: {m.text}"
        for m in conv.messages.all()
        if m.text
    )
    if not transcript:
        messages.error(request, "บทสนทนานี้ยังไม่มีข้อความให้ AI ใช้ร่างใบเสนอราคา")
        return redirect("integrations:conversation", pk=conv.pk)
    catalog = [
        {"code": p.code, "name": p.name, "unit": p.unit, "price": str(p.default_price)}
        for p in Product.objects.filter(is_active=True).order_by("name")[:300]
    ]
    from apps.tenants.quota import QuotaExceeded, gated

    try:
        with gated(conv.tenant, "ai_drafts"):
            draft = draft_quotation_from_text(transcript, catalog=catalog)
    except QuotaExceeded as exc:
        messages.error(request, str(exc))
        return redirect("integrations:conversation", pk=conv.pk)
    except AINotConfigured as exc:
        messages.error(request, str(exc))
        return redirect("integrations:conversation", pk=conv.pk)
    except Exception as exc:  # noqa: BLE001 — surface API/network/parse errors instead of 500
        messages.error(request, f"AI ร่างใบเสนอราคาไม่สำเร็จ: {exc}")
        return redirect("integrations:conversation", pk=conv.pk)
    reference = conv.display_name or (conv.lead.name if conv.lead else "")
    doc = create_quotation_from_ai_draft(
        draft,
        salesperson=request.user,
        reference=reference,
        deal=conv.lead.deal if conv.lead and conv.lead.deal_id else None,
    )
    doc.source_conversation = conv
    if conv.customer_id and not doc.customer_id:
        doc.customer = conv.customer
    doc.save(update_fields=["source_conversation", "customer"])
    messages.success(
        request, f"AI ร่างใบเสนอราคา {doc.doc_number} ให้แล้ว — ตรวจและกดส่งทาง LINE ในหน้านี้"
    )
    return redirect("quotes:quotation_review", pk=doc.pk)


@csrf_exempt
@require_POST
def line_webhook(request: HttpRequest, tenant_slug: str) -> HttpResponse:
    """Inbound LINE Messaging-API webhook — one URL per tenant: ``/integrations/line/webhook/<slug>/``.

    Verifies ``X-Line-Signature`` against the tenant's channel secret, then turns text messages from
    users into leads (apps.integrations.line.process_line_events). Public, no login, CSRF-exempt.
    """
    tenant = get_object_or_404(Tenant, slug=tenant_slug, is_active=True)
    with tenant_context(tenant):
        integration = (
            LineIntegration.objects.filter(is_active=True).exclude(channel_secret="").first()
        )
        if integration is None:
            return HttpResponseBadRequest("LINE integration not configured")

        from linebot.v3 import WebhookParser
        from linebot.v3.exceptions import InvalidSignatureError

        signature = request.headers.get("X-Line-Signature", "")
        try:
            events = WebhookParser(integration.channel_secret).parse(
                request.body.decode("utf-8"), signature
            )
        except InvalidSignatureError:
            return HttpResponseForbidden("bad signature")
        except (ValueError, KeyError, TypeError):
            return HttpResponseBadRequest("malformed payload")
        process_line_events(events)
    return HttpResponse(status=200)
