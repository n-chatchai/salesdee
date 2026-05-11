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
    path("tasks/<int:pk>/done/", views.task_done, name="task_done"),
]
