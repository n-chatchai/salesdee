from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    path("line/webhook/<slug:tenant_slug>/", views.line_webhook, name="line_webhook"),
]
