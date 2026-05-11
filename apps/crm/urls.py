from django.urls import path

from . import views

app_name = "crm"

urlpatterns = [
    path("", views.pipeline, name="pipeline"),
    path("deals/move/", views.move_deal, name="move_deal"),
    path("deals/<int:pk>/", views.deal_detail, name="deal_detail"),
    path("customers/", views.customer_list, name="customers"),
]
