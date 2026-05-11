from django.urls import path

from . import views

app_name = "quotes"

urlpatterns = [
    path("", views.quotation_list, name="quotations"),
    path("new/", views.quotation_create, name="quotation_create"),
    path("<int:pk>/", views.quotation_detail, name="quotation_detail"),
    path("<int:pk>/pdf/", views.quotation_pdf, name="quotation_pdf"),
    path("<int:pk>/edit/", views.quotation_edit, name="quotation_edit"),
    path("<int:pk>/send/", views.quotation_send, name="quotation_send"),
    path("<int:pk>/lines/", views.quotation_lines_partial, name="quotation_lines_partial"),
    path("<int:pk>/lines/add/", views.quotation_add_line, name="quotation_add_line"),
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
