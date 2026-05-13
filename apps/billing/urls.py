from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("invoices/", views.invoices, name="invoices"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/issue-tax/", views.invoice_issue_tax, name="invoice_issue_tax"),
    path("invoices/<int:pk>/cancel/", views.invoice_cancel, name="invoice_cancel"),
    path(
        "from-quotation/<int:quote_pk>/",
        views.quotation_to_invoice,
        name="quotation_to_invoice",
    ),
    path("tax-invoices/", views.tax_invoices, name="tax_invoices"),
    path("tax-invoices/<int:pk>/", views.tax_invoice_detail, name="tax_invoice_detail"),
    path("tax-invoices/<int:pk>/pdf/", views.tax_invoice_pdf, name="tax_invoice_pdf"),
    path("tax-invoices/<int:pk>/cancel/", views.tax_invoice_cancel, name="tax_invoice_cancel"),
    path(
        "tax-invoices/<int:tax_pk>/credit-note/",
        views.credit_note_create,
        name="credit_note_create",
    ),
    path("receipts/", views.receipts, name="receipts"),
    path("receipts/<int:pk>/", views.receipt_detail, name="receipt_detail"),
    path("receipts/<int:pk>/pdf/", views.receipt_pdf, name="receipt_pdf"),
    path("credit-notes/", views.credit_notes, name="credit_notes"),
    path("credit-notes/<int:pk>/", views.credit_note_detail, name="credit_note_detail"),
    path("credit-notes/<int:pk>/pdf/", views.credit_note_pdf, name="credit_note_pdf"),
    path("payments/", views.payments, name="payments"),
    path("payments/new/", views.payment_create, name="payment_create"),
    path("payments/<int:pk>/", views.payment_detail, name="payment_detail"),
    path("reports/ar-aging/", views.ar_aging, name="ar_aging"),
    path("reports/sales-tax/", views.sales_tax_report, name="sales_tax_report"),
]
