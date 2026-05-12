from django.urls import path

from . import views

app_name = "crm"

urlpatterns = [
    path("", views.pipeline, name="pipeline"),
    path("deals/move/", views.move_deal, name="move_deal"),
    path("deals/new/", views.deal_create, name="deal_create"),
    path("deals/<int:pk>/", views.deal_detail, name="deal_detail"),
    path("deals/<int:pk>/edit/", views.deal_edit, name="deal_edit"),
    path("deals/<int:pk>/activities/", views.deal_log_activity, name="deal_log_activity"),
    path("deals/<int:pk>/tasks/", views.deal_add_task, name="deal_add_task"),
    path("customers/", views.customer_list, name="customers"),
    path("customers/new/", views.customer_create, name="customer_create"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("customers/<int:pk>/edit/", views.customer_edit, name="customer_edit"),
    path("tasks/", views.task_list, name="tasks"),
    path("reports/", views.reports, name="reports"),
    path("tasks/<int:pk>/done/", views.task_done, name="task_done"),
    path("leads/", views.lead_list, name="leads"),
    path("leads/new/", views.lead_create, name="lead_create"),
    path("leads/<int:pk>/", views.lead_detail, name="lead_detail"),
    path("leads/<int:pk>/edit/", views.lead_edit, name="lead_edit"),
    path("leads/<int:pk>/convert/", views.lead_convert, name="lead_convert"),
    path("leads/<int:pk>/ai-reply/", views.lead_suggest_reply, name="lead_suggest_reply"),
    path("leads/<int:pk>/send-line/", views.lead_send_line_reply, name="lead_send_line_reply"),
    # Public — no login. Embeddable enquiry form for a tenant.
    path("intake/<slug:tenant_slug>/", views.lead_intake, name="lead_intake"),
]
