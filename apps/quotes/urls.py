from django.urls import path

from . import views

app_name = "quotes"

urlpatterns = [
    path("", views.quotation_list, name="quotations"),
    path("new/", views.quotation_create, name="quotation_create"),
    path("<int:pk>/", views.quotation_detail, name="quotation_detail"),
    path("<int:pk>/pdf/", views.quotation_pdf, name="quotation_pdf"),
    path("<int:pk>/revisions/", views.quotation_revisions, name="quotation_revisions"),
    path(
        "<int:pk>/revisions/<int:revision>/",
        views.quotation_revision_detail,
        name="quotation_revision_detail",
    ),
    path("<int:pk>/edit/", views.quotation_edit, name="quotation_edit"),
    path("<int:pk>/submit/", views.quotation_submit, name="quotation_submit"),
    path("<int:pk>/approve/", views.quotation_approve, name="quotation_approve"),
    path(
        "<int:pk>/reject-approval/",
        views.quotation_reject_approval,
        name="quotation_reject_approval",
    ),
    path("<int:pk>/cancel/", views.quotation_cancel, name="quotation_cancel"),
    path("<int:pk>/reopen/", views.quotation_reopen, name="quotation_reopen"),
    path("<int:pk>/send/", views.quotation_send, name="quotation_send"),
    path("<int:pk>/lines/", views.quotation_lines_partial, name="quotation_lines_partial"),
    path("<int:pk>/lines/add/", views.quotation_add_line, name="quotation_add_line"),
    path("<int:pk>/lines/reorder/", views.quotation_reorder_lines, name="quotation_reorder_lines"),
    path(
        "<int:pk>/lines/<int:line_pk>/edit/",
        views.quotation_line_edit,
        name="quotation_line_edit",
    ),
    path(
        "<int:pk>/lines/<int:line_pk>/delete/",
        views.quotation_delete_line,
        name="quotation_delete_line",
    ),
    path("from-deal/<int:deal_pk>/", views.quotation_from_deal, name="quotation_from_deal"),
]
