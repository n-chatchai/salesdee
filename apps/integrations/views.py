from __future__ import annotations

from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.current_tenant import tenant_context
from apps.tenants.models import Tenant

from .line import process_line_events
from .models import LineIntegration


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
