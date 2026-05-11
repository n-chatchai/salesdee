from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.catalog.models import TaxType
from apps.core.current_tenant import tenant_context
from apps.crm.models import Customer, Deal, PipelineStage, StageKind
from apps.quotes.models import DocStatus, DocType, LineType, SalesDocLine, SalesDocument
from apps.quotes.services import (
    compute_document_totals,
    create_quotation_from_deal,
    next_document_number,
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


def test_quotation_add_and_delete_line(client, user, membership, tenant) -> None:
    doc = _doc(tenant)
    client.force_login(user)
    resp = client.post(
        reverse("quotes:quotation_add_line", args=[doc.pk]),
        {
            "line_type": "item",
            "description": "โต๊ะประชุม 12 ที่นั่ง",
            "quantity": "1",
            "unit_price": "35000",
            "tax_type": TaxType.VAT7,
            "discount_kind": "amount",
        },
    )
    assert resp.status_code == 302
    with tenant_context(tenant):
        assert doc.lines.count() == 1
        line = doc.lines.first()
        assert line is not None
    resp = client.post(reverse("quotes:quotation_delete_line", args=[doc.pk, line.pk]))
    assert resp.status_code == 302
    with tenant_context(tenant):
        assert doc.lines.count() == 0


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
