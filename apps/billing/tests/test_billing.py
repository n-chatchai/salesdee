from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.billing import services
from apps.billing.models import Payment, PaymentAllocation
from apps.core.current_tenant import tenant_context
from apps.crm.models import Customer
from apps.quotes.models import DocStatus, DocType, LineType, SalesDocLine, SalesDocument
from apps.quotes.services import WorkflowError

pytestmark = pytest.mark.django_db


def _quote(tenant, *, customer=None, qty=2, price=Decimal("1000")) -> SalesDocument:
    with tenant_context(tenant):
        customer = customer or Customer.objects.create(
            name="โรงแรม ABC", tax_id="0105551234567", branch_label="สำนักงานใหญ่"
        )
        q = SalesDocument.objects.create(
            doc_type=DocType.QUOTATION,
            customer=customer,
            issue_date=date.today(),
            status=DocStatus.ACCEPTED,
        )
        SalesDocLine.objects.create(
            document=q,
            line_type=LineType.ITEM,
            description="ตู้เสื้อผ้า",
            quantity=qty,
            unit_price=price,
            tax_type="vat7",
        )
        return q


@pytest.fixture
def acc_user(db, tenant):
    from django.contrib.auth import get_user_model

    from apps.accounts.models import Membership, Role

    u = get_user_model().objects.create_user(
        email="acc@wandeedee.test", password="x-1234567890", full_name="บัญชี ทดสอบ"
    )
    Membership.objects.create(user=u, tenant=tenant, role=Role.ACCOUNTING)
    return u


# --- conversion flow ----------------------------------------------------------
def test_quotation_to_invoice_to_tax_to_receipt(tenant) -> None:
    q = _quote(tenant)
    with tenant_context(tenant):
        inv = services.create_invoice_from_quotation(q)
        assert inv.doc_type == DocType.INVOICE
        assert inv.doc_number.startswith("INV-")
        assert inv.source_document_id == q.pk
        assert inv.lines.count() == 1
        from apps.quotes.services import compute_document_totals

        assert compute_document_totals(inv).grand_total == compute_document_totals(q).grand_total

        tax = services.issue_tax_invoice(inv)
        assert tax.doc_type == DocType.TAX_INVOICE
        assert tax.doc_number.startswith("TAX-")
        assert tax.source_document_id == inv.pk
        assert tax.issued_at is not None

        payment = services.record_payment(
            customer=q.customer,
            date=date.today(),
            method="transfer",
            gross_amount=Decimal("2140.00"),
            allocations=[(inv, Decimal("2140.00"))],
            issue_receipt=True,
        )
        assert payment.receipt_document is not None
        assert payment.receipt_document.doc_type == DocType.RECEIPT
        assert payment.receipt_document.doc_number.startswith("RCP-")
        assert services.invoice_outstanding(inv) == Decimal("0.00")


def test_issue_tax_invoice_twice_refused(tenant) -> None:
    q = _quote(tenant)
    with tenant_context(tenant):
        inv = services.create_invoice_from_quotation(q)
        services.issue_tax_invoice(inv)
        with pytest.raises(WorkflowError):
            services.issue_tax_invoice(inv)


# --- gap-free tax-invoice numbering ------------------------------------------
def test_tax_invoice_numbers_gap_free(tenant) -> None:
    with tenant_context(tenant):
        q1 = _quote(tenant, customer=Customer.objects.create(name="A"))
        q2 = _quote(tenant, customer=Customer.objects.create(name="B"))
        q3 = _quote(tenant, customer=Customer.objects.create(name="C"))
        t1 = services.issue_tax_invoice(services.create_invoice_from_quotation(q1))
        t2 = services.issue_tax_invoice(services.create_invoice_from_quotation(q2))
        # cancel t2 — keeps its number
        services.cancel_tax_document(t2, reason="ลูกค้ายกเลิกคำสั่งซื้อ")
        t2.refresh_from_db()
        assert t2.status == DocStatus.CANCELLED
        assert t2.doc_number == t1.doc_number.replace("0001", "0002")
        # next one is +1, not reused
        t3 = services.issue_tax_invoice(services.create_invoice_from_quotation(q3))
        assert t3.doc_number.endswith("0003")


# --- immutability -------------------------------------------------------------
def test_issued_tax_invoice_immutable(tenant) -> None:
    q = _quote(tenant)
    with tenant_context(tenant):
        tax = services.issue_tax_invoice(services.create_invoice_from_quotation(q))
        assert tax.is_editable is False
        tax.notes = "เปลี่ยน"
        with pytest.raises(WorkflowError):
            tax.save()
        # but cancellation is allowed
        services.cancel_tax_document(tax, reason="ออกผิด")
        tax.refresh_from_db()
        assert tax.status == DocStatus.CANCELLED
        assert tax.doc_number  # number kept


# --- payment allocation -------------------------------------------------------
def test_record_payment_validates_outstanding(tenant) -> None:
    q = _quote(tenant)  # grand total = 2 * 1000 * 1.07 = 2140
    with tenant_context(tenant):
        inv = services.create_invoice_from_quotation(q)
        with pytest.raises(WorkflowError):
            services.record_payment(
                customer=q.customer,
                date=date.today(),
                method="cash",
                gross_amount=Decimal("3000"),
                allocations=[(inv, Decimal("3000"))],
            )
        services.record_payment(
            customer=q.customer,
            date=date.today(),
            method="cash",
            gross_amount=Decimal("1000"),
            allocations=[(inv, Decimal("1000"))],
        )
        assert services.invoice_outstanding(inv) == Decimal("1140.00")


# --- credit note --------------------------------------------------------------
def test_credit_note_full_reversal(tenant) -> None:
    q = _quote(tenant)
    with tenant_context(tenant):
        tax = services.issue_tax_invoice(services.create_invoice_from_quotation(q))
        cn = services.create_credit_note(tax, reason="ลดราคาให้ลูกค้า")
        assert cn.doc_type == DocType.CREDIT_NOTE
        assert cn.references_document_id == tax.pk
        assert cn.doc_number.startswith("CN-")
        from apps.quotes.services import compute_document_totals

        assert compute_document_totals(cn).grand_total == -compute_document_totals(tax).grand_total
        # a tax invoice that has a credit note can't be cancelled
        with pytest.raises(WorkflowError):
            services.cancel_tax_document(tax, reason="x")


# --- debit note ---------------------------------------------------------------
def test_debit_note_creates_linked_gap_free_dn(tenant) -> None:
    q = _quote(tenant)
    with tenant_context(tenant):
        tax = services.issue_tax_invoice(services.create_invoice_from_quotation(q))
        dn = services.create_debit_note(tax, reason="คิดราคาน้อยไป 500 บาท")
        assert dn.doc_type == DocType.DEBIT_NOTE
        assert dn.references_document_id == tax.pk
        assert dn.doc_number.startswith("DN-")
        # default: one positive summary line referencing the tax invoice
        first = dn.lines.first()
        assert first is not None
        assert first.unit_price > 0
        from apps.quotes.services import compute_document_totals

        assert compute_document_totals(dn).grand_total > 0
        # gap-free: a second DN gets the next number
        dn2 = services.create_debit_note(tax, reason="ค่าขนส่งเพิ่ม")
        n1 = int(dn.doc_number.rsplit("-", 1)[-1])
        n2 = int(dn2.doc_number.rsplit("-", 1)[-1])
        assert n2 == n1 + 1


# --- AR aging -----------------------------------------------------------------
def test_ar_aging_buckets(tenant) -> None:
    with tenant_context(tenant):
        c = Customer.objects.create(name="ลูกค้าค้าง")
        q = _quote(tenant, customer=c)
        inv = services.create_invoice_from_quotation(q)
        inv.due_date = date(2000, 1, 1)  # long overdue
        inv.save(update_fields=["due_date"])
        data = services.ar_aging(as_of=date.today())
        assert data["totals"]["over_90"] == Decimal("2140.00")
        assert data["totals"]["total"] == Decimal("2140.00")


# --- sales-tax report ---------------------------------------------------------
def test_sales_tax_report_lists_issued_docs(tenant) -> None:
    q = _quote(tenant)
    with tenant_context(tenant):
        tax = services.issue_tax_invoice(services.create_invoice_from_quotation(q))
        data = services.sales_tax_report(year=tax.issue_date.year, month=tax.issue_date.month)
        assert len(data["rows"]) == 1
        row = data["rows"][0]
        assert row["doc_no"] == tax.doc_number
        assert row["buyer_tax_id"] == "0105551234567"
        assert row["value"] == Decimal("2000.00")
        assert row["vat_amount"] == Decimal("140.00")
        assert data["total_vat"] == Decimal("140.00")


# --- views --------------------------------------------------------------------
def test_billing_views_require_login(client) -> None:
    for name in [
        "billing:invoices",
        "billing:tax_invoices",
        "billing:payments",
        "billing:ar_aging",
    ]:
        assert client.get(reverse(name)).status_code == 302


def test_billing_views_render_for_accounting(client, acc_user, tenant) -> None:
    _quote(tenant)
    client.force_login(acc_user)
    for name in [
        "billing:invoices",
        "billing:tax_invoices",
        "billing:receipts",
        "billing:credit_notes",
        "billing:payments",
        "billing:payment_create",
        "billing:ar_aging",
        "billing:sales_tax_report",
    ]:
        assert client.get(reverse(name)).status_code == 200, name


def test_billing_write_forbidden_for_sales(client, user, membership, tenant) -> None:
    # `membership` fixture gives the SALES role
    q = _quote(tenant)
    client.force_login(user)
    resp = client.post(reverse("billing:quotation_to_invoice", args=[q.pk]))
    assert resp.status_code == 403


def test_quotation_to_invoice_view(client, acc_user, tenant) -> None:
    q = _quote(tenant)
    client.force_login(acc_user)
    resp = client.post(reverse("billing:quotation_to_invoice", args=[q.pk]))
    assert resp.status_code == 302
    with tenant_context(tenant):
        assert SalesDocument.objects.filter(doc_type=DocType.INVOICE).count() == 1


def test_tax_invoice_pdf(client, acc_user, tenant) -> None:
    q = _quote(tenant)
    with tenant_context(tenant):
        tax = services.issue_tax_invoice(services.create_invoice_from_quotation(q))
    client.force_login(acc_user)
    resp = client.get(reverse("billing:tax_invoice_pdf", args=[tax.pk]))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


# --- tenant isolation ---------------------------------------------------------
def test_payment_tenant_isolation(tenant, other_tenant) -> None:
    with tenant_context(tenant):
        c = Customer.objects.create(name="C")
        p = Payment.objects.create(customer=c, date=date.today(), gross_amount=Decimal("100"))
        PaymentAllocation.objects.create(
            payment=p,
            invoice=SalesDocument.objects.create(
                doc_type=DocType.INVOICE, customer=c, issue_date=date.today()
            ),
            amount=Decimal("100"),
        )
    with tenant_context(other_tenant):
        assert Payment.objects.count() == 0
        assert PaymentAllocation.objects.count() == 0
    with tenant_context(tenant):
        assert Payment.objects.count() == 1
        assert PaymentAllocation.objects.count() == 1
