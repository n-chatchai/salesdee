"""Quota check + counter increment + plan-cap enforcement (Phase B)."""

from __future__ import annotations

import pytest

from apps.tenants import quota
from apps.tenants.models import Usage


def test_current_period_is_yyyymm_int() -> None:
    p = quota.current_period()
    assert 202000 <= p <= 210000  # sanity
    assert 1 <= p % 100 <= 12


def test_trial_plan_caps_ai_drafts(tenant) -> None:
    """Trial plan = 50 AI drafts/month. New tenant under cap."""
    ok, used, limit = quota.check_quota(tenant, "ai_drafts")
    assert ok is True
    assert used == 0
    assert limit == 50


def test_business_plan_is_unlimited(tenant) -> None:
    tenant.plan = "business"
    tenant.save(update_fields=["plan"])
    ok, used, limit = quota.check_quota(tenant, "ai_drafts")
    assert ok is True
    assert limit == -1


def test_increment_usage_counts_atomically(tenant) -> None:
    quota.increment_usage(tenant, "line_msgs", 3)
    quota.increment_usage(tenant, "line_msgs")
    row = Usage.all_tenants.get(tenant=tenant, period=quota.current_period(), kind="line_msgs")
    assert row.count == 4


def test_enforce_quota_raises_at_cap(tenant) -> None:
    tenant.plan = "starter"  # tax_invoices=0
    tenant.save(update_fields=["plan"])
    with pytest.raises(quota.QuotaExceeded) as exc:
        quota.enforce_quota(tenant, "tax_invoices")
    assert exc.value.kind == "tax_invoices"
    assert "ใบกำกับภาษี" in str(exc.value)


def test_gated_context_manager_increments_on_success(tenant) -> None:
    with quota.gated(tenant, "ai_drafts"):
        pass  # successful body → increment
    ok, used, _ = quota.check_quota(tenant, "ai_drafts")
    assert used == 1


def test_gated_does_not_increment_on_failure(tenant) -> None:
    with pytest.raises(RuntimeError), quota.gated(tenant, "ai_drafts"):
        raise RuntimeError("body failed")
    _, used, _ = quota.check_quota(tenant, "ai_drafts")
    assert used == 0


def test_gated_raises_quota_exceeded(tenant) -> None:
    tenant.plan = "starter"  # tax_invoices=0
    tenant.save(update_fields=["plan"])
    with pytest.raises(quota.QuotaExceeded), quota.gated(tenant, "tax_invoices"):
        pass


def test_near_cap_returns_kinds_above_threshold(tenant) -> None:
    # Trial: ai_drafts=50. Bump to 40 → 80%, should appear.
    quota.increment_usage(tenant, "ai_drafts", 40)
    warning = quota.near_cap(tenant)
    kinds = {c.kind for c in warning}
    assert "ai_drafts" in kinds
    # tax_invoices is 0/10 — below threshold, not in warning
    assert "tax_invoices" not in kinds


def test_caps_for_tenant_returns_all_kinds(tenant) -> None:
    caps = quota.caps_for_tenant(tenant)
    kinds = {c.kind for c in caps}
    assert kinds == {"line_msgs", "ai_drafts", "tax_invoices"}


def test_unknown_kind_is_unlimited(tenant) -> None:
    ok, used, limit = quota.check_quota(tenant, "wat_no_such_thing")
    assert (ok, used, limit) == (True, 0, -1)


def test_usage_is_tenant_isolated(tenant, other_tenant) -> None:
    """Counters live per-tenant — bumping one must not be visible from the other."""
    quota.increment_usage(tenant, "ai_drafts", 5)
    quota.increment_usage(other_tenant, "ai_drafts", 1)
    _, used_a, _ = quota.check_quota(tenant, "ai_drafts")
    _, used_b, _ = quota.check_quota(other_tenant, "ai_drafts")
    assert used_a == 5
    assert used_b == 1


# ─── wiring: counters fire from the production code paths ───────────────────


def test_line_inbound_text_bumps_line_msgs(tenant, monkeypatch) -> None:
    """LINE webhook → `_record_inbound` increments the line_msgs counter."""
    from apps.core.current_tenant import tenant_context
    from apps.integrations.line import _record_inbound

    monkeypatch.setattr("apps.integrations.line.fetch_line_profile_name", lambda *a, **k: "")
    with tenant_context(tenant):
        _record_inbound("Usender1", text="สนใจโต๊ะทำงาน")
        _record_inbound("Usender1", text="ราคาเท่าไร")
    _, used, _ = quota.check_quota(tenant, "line_msgs")
    assert used == 2


def test_issue_tax_invoice_blocked_at_cap(tenant) -> None:
    """Starter plan caps tax_invoices=0 — issuing must raise QuotaExceeded."""
    from datetime import date

    from apps.billing.services import issue_tax_invoice
    from apps.core.current_tenant import tenant_context
    from apps.crm.models import Customer
    from apps.quotes.models import DocStatus, DocType, SalesDocument

    tenant.plan = "starter"
    tenant.save(update_fields=["plan"])
    with tenant_context(tenant):
        customer = Customer.objects.create(name="ลูกค้า")
        inv = SalesDocument.objects.create(
            doc_type=DocType.INVOICE,
            doc_number="INV-001",
            customer=customer,
            issue_date=date.today(),
            status=DocStatus.SENT,
        )
        with pytest.raises(quota.QuotaExceeded):
            issue_tax_invoice(inv)


def test_member_invite_blocked_at_user_cap(client, tenant) -> None:
    """Starter plan caps users=2 — inviting past that fails with a flash."""
    from django.contrib.auth import get_user_model
    from django.urls import reverse

    from apps.accounts.models import Membership, Role

    tenant.plan = "starter"
    tenant.save(update_fields=["plan"])
    owner = get_user_model().objects.create_user(email="o@x.test", password="pw-123456789")
    Membership.objects.create(user=owner, tenant=tenant, role=Role.OWNER)
    # second user fills the 2-user cap
    other = get_user_model().objects.create_user(email="s@x.test", password="pw-x")
    Membership.objects.create(user=other, tenant=tenant, role=Role.SALES)
    client.force_login(owner)
    resp = client.post(
        reverse("workspace:settings_members"),
        {"email": "third@x.test", "role": Role.SALES},
    )
    assert resp.status_code == 302
    assert not get_user_model().objects.filter(email="third@x.test").exists()


def test_billing_gate_blocks_growth_plan(client, tenant) -> None:
    """Growth plan = no billing module. /billing/invoices/ returns 402 + upgrade page."""
    from django.contrib.auth import get_user_model
    from django.urls import reverse

    from apps.accounts.models import Membership, Role

    tenant.plan = "growth"
    tenant.save(update_fields=["plan"])
    owner = get_user_model().objects.create_user(email="o@x.test", password="pw-123456789")
    Membership.objects.create(user=owner, tenant=tenant, role=Role.OWNER)
    client.force_login(owner)
    resp = client.get(reverse("billing:invoices"))
    assert resp.status_code == 402
    assert "อัปเกรดเป็น Pro" in resp.content.decode()


def test_billing_gate_allows_pro_plan(client, tenant) -> None:
    """Pro plan = billing module enabled. /billing/invoices/ renders normally."""
    from django.contrib.auth import get_user_model
    from django.urls import reverse

    from apps.accounts.models import Membership, Role

    tenant.plan = "pro"
    tenant.save(update_fields=["plan"])
    owner = get_user_model().objects.create_user(email="o@x.test", password="pw-123456789")
    Membership.objects.create(user=owner, tenant=tenant, role=Role.OWNER)
    client.force_login(owner)
    resp = client.get(reverse("billing:invoices"))
    assert resp.status_code == 200


def test_member_invite_growth_plan_allows_more(client, tenant) -> None:
    """Growth caps users=5 — a third invite succeeds (still under cap)."""
    from django.contrib.auth import get_user_model
    from django.urls import reverse

    from apps.accounts.models import Membership, Role

    tenant.plan = "growth"
    tenant.save(update_fields=["plan"])
    owner = get_user_model().objects.create_user(email="o@x.test", password="pw-123456789")
    Membership.objects.create(user=owner, tenant=tenant, role=Role.OWNER)
    client.force_login(owner)
    resp = client.post(
        reverse("workspace:settings_members"),
        {"email": "new@x.test", "role": Role.SALES},
    )
    assert resp.status_code == 302
    assert get_user_model().objects.filter(email="new@x.test").exists()
