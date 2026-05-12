from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import TaxType
from apps.core.current_tenant import tenant_context
from apps.crm.models import Contact, Customer, Deal, PipelineStage, StageKind, Task
from apps.quotes.models import (
    CustomerResponse,
    DiscountKind,
    DocStatus,
    DocType,
    LineType,
    PriceMode,
    QuotationRevision,
    QuotationShareLink,
    SalesDocLine,
    SalesDocument,
)
from apps.quotes.services import (
    WorkflowError,
    approve_quotation,
    can_approve,
    compute_document_totals,
    create_quotation_from_deal,
    expire_overdue_quotations,
    get_or_create_share_link,
    mark_sent,
    next_document_number,
    reject_approval,
    reopen_quotation,
    submit_quotation,
)

pytestmark = pytest.mark.django_db


def _doc(tenant, **kwargs) -> SalesDocument:
    with tenant_context(tenant):
        customer = kwargs.pop("customer", None) or Customer.objects.create(name="ลูกค้าทดสอบ")
        return SalesDocument.objects.create(
            doc_type=DocType.QUOTATION, customer=customer, issue_date=date.today(), **kwargs
        )


def _line(tenant, doc, **kwargs) -> SalesDocLine:
    with tenant_context(tenant):
        kwargs.setdefault("line_type", LineType.ITEM)
        kwargs.setdefault("description", "รายการ")
        return SalesDocLine.objects.create(document=doc, **kwargs)


# --- document numbers ---------------------------------------------------------
def test_next_document_number_increments_per_tenant(tenant, other_tenant) -> None:
    with tenant_context(tenant):
        a1 = next_document_number(DocType.QUOTATION, prefix="QT")
        a2 = next_document_number(DocType.QUOTATION, prefix="QT")
    with tenant_context(other_tenant):
        b1 = next_document_number(DocType.QUOTATION, prefix="QT")
    assert a1.startswith("QT-") and a1.endswith("-0001")
    assert a2.endswith("-0002") and a1[:-4] == a2[:-4]
    assert b1.endswith("-0001")  # other tenant has its own counter


# --- totals engine ------------------------------------------------------------
def test_compute_totals_basic(tenant) -> None:
    doc = _doc(tenant, end_discount_value=Decimal("100"))  # AMOUNT (default)
    _line(
        tenant,
        doc,
        quantity=Decimal("2"),
        unit_price=Decimal("1000"),
        tax_type=TaxType.VAT7,
        withholding_rate=Decimal("3"),
    )
    _line(tenant, doc, quantity=Decimal("1"), unit_price=Decimal("500"), tax_type=TaxType.VAT0)
    with tenant_context(tenant):
        t = compute_document_totals(doc)
    assert t.subtotal == Decimal("2500.00")
    assert t.end_discount == Decimal("100.00")
    assert t.after_discount == Decimal("2400.00")
    assert t.base_vat7 == Decimal("1920.00")
    assert t.vat_amount == Decimal("134.40")
    assert t.grand_total == Decimal("2534.40")
    assert t.withholding_estimate == Decimal("57.60")
    assert t.net_expected == Decimal("2476.80")
    assert t.has_zero_rated is True
    assert t.amount_in_words == "สองพันห้าร้อยสามสิบสี่บาทสี่สิบสตางค์"


def test_compute_totals_inclusive_vat(tenant) -> None:
    doc = _doc(tenant, price_mode=PriceMode.INCLUSIVE)
    _line(tenant, doc, quantity=Decimal("1"), unit_price=Decimal("1070"), tax_type=TaxType.VAT7)
    with tenant_context(tenant):
        t = compute_document_totals(doc)
    assert t.inclusive is True
    assert t.subtotal == Decimal("1070.00")
    assert t.base_vat7 == Decimal("1000.00")
    assert t.vat_amount == Decimal("70.00")
    assert t.grand_total == Decimal("1070.00")
    assert t.rounding == Decimal("0.00")


def test_compute_totals_inclusive_vat_with_end_discount(tenant) -> None:
    doc = _doc(
        tenant,
        price_mode=PriceMode.INCLUSIVE,
        end_discount_kind=DiscountKind.PERCENT,
        end_discount_value=Decimal("10"),
    )
    _line(tenant, doc, quantity=Decimal("1"), unit_price=Decimal("1070"), tax_type=TaxType.VAT7)
    with tenant_context(tenant):
        t = compute_document_totals(doc)
    assert t.after_discount == Decimal("963.00")
    assert t.base_vat7 == Decimal("900.00")
    assert t.vat_amount == Decimal("63.00")
    assert t.grand_total == Decimal("963.00")


def test_compute_totals_exclusive_is_unchanged(tenant) -> None:
    """Exclusive mode (the default) must behave exactly as before the inclusive refactor."""
    doc = _doc(tenant, end_discount_value=Decimal("100"))
    _line(
        tenant,
        doc,
        quantity=Decimal("2"),
        unit_price=Decimal("1000"),
        tax_type=TaxType.VAT7,
        withholding_rate=Decimal("3"),
    )
    with tenant_context(tenant):
        t = compute_document_totals(doc)
    assert t.inclusive is False
    assert t.subtotal == Decimal("2000.00")
    assert t.after_discount == Decimal("1900.00")
    assert t.base_vat7 == Decimal("1900.00")
    assert t.vat_amount == Decimal("133.00")
    assert t.grand_total == Decimal("2033.00")
    assert t.withholding_estimate == Decimal("57.00")
    assert t.rounding == Decimal("0.00")


def test_compute_totals_ignores_heading_and_note_lines(tenant) -> None:
    doc = _doc(tenant)
    _line(tenant, doc, line_type=LineType.HEADING, description="ห้องประชุม")
    _line(tenant, doc, line_type=LineType.NOTE, description="ราคารวมติดตั้ง")
    _line(tenant, doc, quantity=Decimal("1"), unit_price=Decimal("100"), tax_type=TaxType.VAT7)
    with tenant_context(tenant):
        t = compute_document_totals(doc)
    assert t.subtotal == Decimal("100.00")
    assert t.grand_total == Decimal("107.00")
    assert t.has_zero_rated is False


# --- create from deal ---------------------------------------------------------
def test_create_quotation_from_deal(tenant, user, membership) -> None:
    with tenant_context(tenant):
        customer = Customer.objects.create(name="โรงแรม ABC")
        stage = PipelineStage.objects.filter(kind=StageKind.OPEN).order_by("order")[0]
        deal = Deal.objects.create(name="เฟอร์นิเจอร์ล็อบบี้", customer=customer, stage=stage)
        doc = create_quotation_from_deal(deal, salesperson=user)
        assert doc.doc_number.startswith("QT-")
        assert doc.customer_id == customer.pk
        assert doc.deal_id == deal.pk
        assert doc.status == DocStatus.DRAFT


# --- views --------------------------------------------------------------------
def test_quotation_create_view(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        customer = Customer.objects.create(name="ลูกค้า X")
    client.force_login(user)
    resp = client.post(
        reverse("quotes:quotation_create"),
        {
            "customer": customer.pk,
            "issue_date": date.today().isoformat(),
            "end_discount_kind": "amount",
        },
    )
    assert resp.status_code == 302
    with tenant_context(tenant):
        doc = SalesDocument.objects.latest("created_at")
        assert doc.doc_number.startswith("QT-")
    assert resp.url == reverse("quotes:quotation_detail", args=[doc.pk])


def test_quotation_create_view_with_inclusive_price_mode(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        customer = Customer.objects.create(name="ลูกค้า Incl")
    client.force_login(user)
    resp = client.post(
        reverse("quotes:quotation_create"),
        {
            "customer": customer.pk,
            "issue_date": date.today().isoformat(),
            "price_mode": PriceMode.INCLUSIVE,
            "end_discount_kind": "amount",
        },
    )
    assert resp.status_code == 302
    with tenant_context(tenant):
        doc = SalesDocument.objects.latest("created_at")
    assert doc.price_mode == PriceMode.INCLUSIVE


def test_quotation_add_and_delete_line_htmx(client, user, membership, tenant) -> None:
    doc = _doc(tenant)
    client.force_login(user)
    resp = client.post(
        reverse("quotes:quotation_add_line", args=[doc.pk]),
        {
            "line_type": "item",
            "description": "โต๊ะประชุม 12 ที่นั่ง",
            "quantity": "1",
            "unit_price": "35000",
        },
    )
    assert resp.status_code == 200  # htmx -> the #quote-lines partial
    assert "โต๊ะประชุม 12 ที่นั่ง" in resp.content.decode()
    with tenant_context(tenant):
        assert doc.lines.count() == 1
        line = doc.lines.first()
        assert line is not None
    resp = client.post(reverse("quotes:quotation_delete_line", args=[doc.pk, line.pk]))
    assert resp.status_code == 200
    with tenant_context(tenant):
        assert doc.lines.count() == 0


def test_quotation_lines_partial_renders(client, user, membership, tenant) -> None:
    doc = _doc(tenant)
    client.force_login(user)
    resp = client.get(reverse("quotes:quotation_lines_partial", args=[doc.pk]))
    assert resp.status_code == 200
    assert "เพิ่มรายการ" in resp.content.decode()


def test_quotation_line_edit_get_and_post(client, user, membership, tenant) -> None:
    doc = _doc(tenant)
    _line(tenant, doc, description="เก่า", quantity=Decimal("1"), unit_price=Decimal("100"))
    with tenant_context(tenant):
        line = doc.lines.get()
    client.force_login(user)
    get_resp = client.get(reverse("quotes:quotation_line_edit", args=[doc.pk, line.pk]))
    assert get_resp.status_code == 200
    assert "เก่า" in get_resp.content.decode()  # the bound edit form
    post_resp = client.post(
        reverse("quotes:quotation_line_edit", args=[doc.pk, line.pk]),
        {"line_type": "item", "description": "ใหม่", "quantity": "3", "unit_price": "250"},
    )
    assert post_resp.status_code == 200
    with tenant_context(tenant):
        line.refresh_from_db()
        assert line.description == "ใหม่"
        assert line.quantity == Decimal("3")
        assert line.unit_price == Decimal("250")


def test_add_line_with_product_fills_defaults(client, user, membership, tenant) -> None:
    from apps.catalog.models import Product

    with tenant_context(tenant):
        prod = Product.objects.create(
            name="โต๊ะ X", default_price=Decimal("1200"), unit="ตัว", tax_type=TaxType.VAT7
        )
        doc = SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            customer=Customer.objects.create(name="C"),
            issue_date=date.today(),
        )
    client.force_login(user)
    resp = client.post(
        reverse("quotes:quotation_add_line", args=[doc.pk]),
        {"line_type": "item", "product": prod.pk},
    )
    assert resp.status_code == 200
    with tenant_context(tenant):
        line = doc.lines.get()
        assert line.unit_price == Decimal("1200")
        assert line.description == "โต๊ะ X"
        assert line.unit == "ตัว"


def test_quotation_list_and_detail_render(client, user, membership, tenant) -> None:
    doc = _doc(tenant)
    _line(tenant, doc, description="ตู้ล็อกเกอร์", quantity=Decimal("3"), unit_price=Decimal("4500"))
    with tenant_context(tenant):
        doc.doc_number = "QT-2569-0001"
        doc.save()
    client.force_login(user)
    assert "QT-2569-0001" in client.get(reverse("quotes:quotations")).content.decode()
    body = client.get(reverse("quotes:quotation_detail", args=[doc.pk])).content.decode()
    assert "QT-2569-0001" in body
    assert "ตู้ล็อกเกอร์" in body


def test_quotation_from_deal_view(client, user, membership, tenant) -> None:
    with tenant_context(tenant):
        deal = Deal.objects.create(name="ดีลทดสอบ")
    client.force_login(user)
    resp = client.post(reverse("quotes:quotation_from_deal", args=[deal.pk]))
    assert resp.status_code == 302
    with tenant_context(tenant):
        assert SalesDocument.objects.filter(deal=deal).count() == 1


def test_quotation_pdf_renders(client, user, membership, tenant) -> None:
    doc = _doc(tenant)
    _line(
        tenant,
        doc,
        description="โต๊ะประชุม 12 ที่นั่ง",
        quantity=Decimal("1"),
        unit_price=Decimal("35000"),
    )
    with tenant_context(tenant):
        doc.doc_number = "QT-2569-0009"
        doc.save()
    client.force_login(user)
    resp = client.get(reverse("quotes:quotation_pdf", args=[doc.pk]))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


# --- sending / public share link ---------------------------------------------
def _doc_with_contact(tenant) -> tuple[SalesDocument, Contact]:
    with tenant_context(tenant):
        customer = Customer.objects.create(name="โรงเรียน บี")
        contact = Contact.objects.create(customer=customer, name="คุณวิภา", email="wipa@school.test")
        doc = SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            customer=customer,
            contact=contact,
            issue_date=date.today(),
            doc_number="QT-2569-0007",
        )
        return doc, contact


def test_quotation_send_creates_link_marks_sent_and_follow_up(
    client, user, membership, tenant
) -> None:
    doc, _contact = _doc_with_contact(tenant)
    client.force_login(user)
    resp = client.post(reverse("quotes:quotation_send", args=[doc.pk]))
    assert resp.status_code == 302
    with tenant_context(tenant):
        doc.refresh_from_db()
        assert doc.status == DocStatus.SENT
        assert doc.sent_at is not None
        link = QuotationShareLink.objects.get(document=doc)
        assert link.is_valid()
        assert Task.objects.filter(customer=doc.customer, kind="follow_up").exists()


def test_public_quotation_view_anonymous(client, tenant) -> None:
    doc, _ = _doc_with_contact(tenant)
    with tenant_context(tenant):
        link = get_or_create_share_link(doc, created_by=None)
    resp = client.get(reverse("public_quotation", args=[link.token]))
    assert resp.status_code == 200
    assert "QT-2569-0007" in resp.content.decode()


def test_public_quotation_respond_accept(client, tenant) -> None:
    doc, _ = _doc_with_contact(tenant)
    with tenant_context(tenant):
        link = get_or_create_share_link(doc, created_by=None)
    resp = client.post(
        reverse("public_quotation_respond", args=[link.token]),
        {"response": CustomerResponse.ACCEPTED, "signed_name": "วิภา ผู้ซื้อ", "note": ""},
    )
    assert resp.status_code == 200
    assert "ได้รับคำตอบ" in resp.content.decode()
    with tenant_context(tenant):
        doc.refresh_from_db()
        assert doc.customer_response == CustomerResponse.ACCEPTED
        assert doc.status == DocStatus.ACCEPTED
        assert doc.customer_signed_name == "วิภา ผู้ซื้อ"


def test_public_quotation_invalid_token(client) -> None:
    resp = client.get(reverse("public_quotation", args=["no-such-token"]))
    assert resp.status_code == 200
    assert "หมดอายุ" in resp.content.decode()


def test_public_quotation_expired_link(client, tenant) -> None:
    doc, _ = _doc_with_contact(tenant)
    with tenant_context(tenant):
        QuotationShareLink.objects.create(
            tenant_id=doc.tenant_id,
            document=doc,
            token="expired-tok",
            expires_at=timezone.now() - timedelta(days=1),
        )
    resp = client.get(reverse("public_quotation", args=["expired-tok"]))
    assert resp.status_code == 200
    assert "หมดอายุ" in resp.content.decode()


def test_public_quotation_pdf_anonymous(client, tenant) -> None:
    doc, _ = _doc_with_contact(tenant)
    _line(tenant, doc, description="โต๊ะ", quantity=Decimal("1"), unit_price=Decimal("1000"))
    with tenant_context(tenant):
        link = get_or_create_share_link(doc, created_by=None)
    resp = client.get(reverse("public_quotation_pdf", args=[link.token]))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


# --- document lifecycle / discount-approval workflow -------------------------
def _manager(tenant):
    from django.contrib.auth import get_user_model

    from apps.accounts.models import Membership, Role

    u = get_user_model().objects.create_user(
        email="mgr@wandeedee.test", password="testpass-12345", full_name="ผู้จัดการ ทดสอบ"
    )
    Membership.objects.create(user=u, tenant=tenant, role=Role.MANAGER)
    return u


def test_submit_without_excess_discount_goes_ready(tenant, user, membership) -> None:
    doc = _doc(tenant)
    _line(tenant, doc, quantity=Decimal("1"), unit_price=Decimal("1000"))
    with tenant_context(tenant):
        assert submit_quotation(doc, user=user) == DocStatus.READY
    assert doc.status == DocStatus.READY


def test_submit_with_excess_discount_needs_approval(tenant, user, membership) -> None:
    with tenant_context(tenant):
        membership.max_discount_percent = Decimal("5")
        membership.save()
    doc = _doc(tenant)
    _line(
        tenant,
        doc,
        quantity=Decimal("1"),
        unit_price=Decimal("1000"),
        discount_kind=DiscountKind.PERCENT,
        discount_value=Decimal("20"),
    )
    with tenant_context(tenant):
        assert submit_quotation(doc, user=user) == DocStatus.PENDING_APPROVAL


def test_manager_can_approve_salesperson_cannot(tenant, user, membership) -> None:
    mgr = _manager(tenant)
    with tenant_context(tenant):
        membership.max_discount_percent = Decimal("0")
        membership.save()
    doc = _doc(tenant)
    _line(
        tenant,
        doc,
        unit_price=Decimal("1000"),
        discount_kind=DiscountKind.PERCENT,
        discount_value=Decimal("10"),
    )
    with tenant_context(tenant):
        assert submit_quotation(doc, user=user) == DocStatus.PENDING_APPROVAL
        assert can_approve(mgr, tenant.pk) is True
        assert can_approve(user, tenant.pk) is False
        approve_quotation(doc, user=mgr)
    assert doc.status == DocStatus.READY
    assert doc.approved_by_id == mgr.pk
    assert doc.approved_at is not None


def test_reject_approval_returns_to_draft(tenant, user, membership) -> None:
    with tenant_context(tenant):
        membership.max_discount_percent = Decimal("0")
        membership.save()
    doc = _doc(tenant)
    _line(
        tenant,
        doc,
        unit_price=Decimal("100"),
        discount_kind=DiscountKind.PERCENT,
        discount_value=Decimal("5"),
    )
    with tenant_context(tenant):
        submit_quotation(doc, user=user)
        reject_approval(doc, user=user)
    assert doc.status == DocStatus.DRAFT


def test_cannot_submit_a_sent_quotation(tenant) -> None:
    doc = _doc(tenant, status=DocStatus.SENT)
    with tenant_context(tenant), pytest.raises(WorkflowError):
        submit_quotation(doc, user=None)


def test_reopen_bumps_revision_and_clears_response(tenant) -> None:
    doc = _doc(
        tenant,
        status=DocStatus.ACCEPTED,
        sent_at=timezone.now(),
        customer_response=CustomerResponse.ACCEPTED,
        customer_signed_name="ลูกค้า",
    )
    with tenant_context(tenant):
        reopen_quotation(doc)
    assert doc.status == DocStatus.DRAFT
    assert doc.revision == 1
    assert doc.sent_at is None
    assert doc.customer_response == ""
    assert doc.customer_signed_name == ""


def test_reopen_rejected_when_still_draft(tenant) -> None:
    doc = _doc(tenant)  # DRAFT
    with tenant_context(tenant), pytest.raises(WorkflowError):
        reopen_quotation(doc)


def test_expire_overdue_quotations(tenant) -> None:
    overdue = _doc(tenant, status=DocStatus.SENT, valid_until=date.today() - timedelta(days=1))
    fresh = _doc(tenant, status=DocStatus.SENT, valid_until=date.today() + timedelta(days=5))
    draft_overdue = _doc(
        tenant, status=DocStatus.DRAFT, valid_until=date.today() - timedelta(days=9)
    )
    with tenant_context(tenant):
        n = expire_overdue_quotations()
        overdue.refresh_from_db()
        fresh.refresh_from_db()
        draft_overdue.refresh_from_db()
    assert n == 1
    assert overdue.status == DocStatus.EXPIRED
    assert fresh.status == DocStatus.SENT
    assert draft_overdue.status == DocStatus.DRAFT  # only READY/SENT expire


def test_editing_a_sent_quotation_is_blocked(client, user, membership, tenant) -> None:
    doc = _doc(tenant, status=DocStatus.SENT)
    client.force_login(user)
    # editing the header redirects back to detail with an error message
    resp = client.get(reverse("quotes:quotation_edit", args=[doc.pk]))
    assert resp.status_code == 302
    assert resp.url == reverse("quotes:quotation_detail", args=[doc.pk])
    # adding a line is forbidden
    resp = client.post(
        reverse("quotes:quotation_add_line", args=[doc.pk]),
        {"line_type": "item", "description": "x", "quantity": "1", "unit_price": "1"},
    )
    assert resp.status_code == 403


def test_submit_and_approve_views(client, user, membership, tenant) -> None:
    mgr = _manager(tenant)
    with tenant_context(tenant):
        membership.max_discount_percent = Decimal("0")
        membership.save()
    doc = _doc(tenant)
    _line(
        tenant,
        doc,
        unit_price=Decimal("1000"),
        discount_kind=DiscountKind.PERCENT,
        discount_value=Decimal("10"),
    )
    client.force_login(user)
    client.post(reverse("quotes:quotation_submit", args=[doc.pk]))
    with tenant_context(tenant):
        doc.refresh_from_db()
    assert doc.status == DocStatus.PENDING_APPROVAL
    # the salesperson cannot approve
    assert client.post(reverse("quotes:quotation_approve", args=[doc.pk])).status_code == 403
    # the manager can
    client.force_login(mgr)
    resp = client.post(reverse("quotes:quotation_approve", args=[doc.pk]))
    assert resp.status_code == 302
    with tenant_context(tenant):
        doc.refresh_from_db()
    assert doc.status == DocStatus.READY
    assert doc.approved_by_id == mgr.pk


def test_reopen_view(client, user, membership, tenant) -> None:
    doc = _doc(tenant, status=DocStatus.REJECTED)
    client.force_login(user)
    resp = client.post(reverse("quotes:quotation_reopen", args=[doc.pk]))
    assert resp.status_code == 302
    with tenant_context(tenant):
        doc.refresh_from_db()
    assert doc.status == DocStatus.DRAFT
    assert doc.revision == 1


def test_expire_quotations_command(tenant) -> None:
    from django.core.management import call_command

    overdue = _doc(tenant, status=DocStatus.SENT, valid_until=date.today() - timedelta(days=2))
    call_command("expire_quotations")
    with tenant_context(tenant):
        overdue.refresh_from_db()
    assert overdue.status == DocStatus.EXPIRED


# --- revisions (snapshot on send) --------------------------------------------
def test_sending_records_a_revision_snapshot(tenant, user, membership) -> None:
    doc = _doc(tenant, status=DocStatus.READY, doc_number="QT-2569-0100")
    _line(tenant, doc, quantity=Decimal("2"), unit_price=Decimal("1000"), tax_type=TaxType.VAT7)
    with tenant_context(tenant):
        mark_sent(doc, user=user)
        assert doc.status == DocStatus.SENT
        rev = QuotationRevision.objects.get(document=doc, revision=0)
    assert rev.snapshot["doc_number"] == "QT-2569-0100"
    assert rev.snapshot["totals"]["grand_total"] == "2140.00"
    assert len(rev.snapshot["lines"]) == 1
    assert rev.changed_by_id == user.pk


def test_reopen_with_reason_then_resend_records_second_revision(tenant, user, membership) -> None:
    doc = _doc(tenant, status=DocStatus.READY)
    _line(tenant, doc, quantity=Decimal("1"), unit_price=Decimal("1000"))
    with tenant_context(tenant):
        mark_sent(doc, user=user)
        reopen_quotation(doc, reason="ลูกค้าขอเปลี่ยนสี")
        assert doc.status == DocStatus.DRAFT and doc.revision == 1
        line = doc.lines.get()
        line.unit_price = Decimal("1200")
        line.save()
        submit_quotation(doc, user=user)
        mark_sent(doc, user=user)
        assert doc.revisions.count() == 2
        rev1 = doc.revisions.get(revision=1)
    assert rev1.reason == "ลูกค้าขอเปลี่ยนสี"
    assert rev1.snapshot["totals"]["grand_total"] == "1284.00"


def test_resend_does_not_create_a_second_revision(tenant, user, membership) -> None:
    doc = _doc(tenant, status=DocStatus.READY)
    _line(tenant, doc, unit_price=Decimal("500"))
    with tenant_context(tenant):
        mark_sent(doc, user=user)
        mark_sent(doc, user=user)  # resend — status is already SENT
        assert doc.revisions.count() == 1


def test_quotation_revisions_views(client, user, membership, tenant) -> None:
    doc = _doc(tenant, status=DocStatus.READY, doc_number="QT-2569-0200")
    _line(tenant, doc, quantity=Decimal("1"), unit_price=Decimal("3000"))
    with tenant_context(tenant):
        mark_sent(doc, user=user)
    client.force_login(user)
    assert (
        "Rev.0" in client.get(reverse("quotes:quotation_revisions", args=[doc.pk])).content.decode()
    )
    body = client.get(
        reverse("quotes:quotation_revision_detail", args=[doc.pk, 0])
    ).content.decode()
    assert "QT-2569-0200" in body
    assert (
        "ประวัติเวอร์ชัน"
        in client.get(reverse("quotes:quotation_detail", args=[doc.pk])).content.decode()
    )


def test_quotation_revision_tenant_isolation(tenant, other_tenant, user, membership) -> None:
    doc = _doc(tenant, status=DocStatus.READY)
    _line(tenant, doc, unit_price=Decimal("100"))
    with tenant_context(tenant):
        mark_sent(doc, user=user)
        assert QuotationRevision.objects.count() == 1
    with tenant_context(other_tenant):
        assert QuotationRevision.objects.count() == 0
