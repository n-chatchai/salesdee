from django.urls import path

from . import views

app_name = "workspace"

urlpatterns = [
    path("", views.settings_hub, name="settings_hub"),
    path("welcome/", views.onboarding, name="onboarding"),
    path("status/", views.system_status, name="system_status"),
    path("company/", views.settings_company, name="settings_company"),
    path("line/", views.settings_line, name="settings_line"),
    path("pipeline/", views.settings_pipeline, name="settings_pipeline"),
    path("pipeline/<int:pk>/edit/", views.pipeline_stage_edit, name="pipeline_stage_edit"),
    path("pipeline/reorder/", views.pipeline_reorder, name="pipeline_reorder"),
    path("numbering/", views.settings_numbering, name="settings_numbering"),
    path("members/", views.settings_members, name="settings_members"),
    path("members/<int:pk>/edit/", views.member_edit, name="member_edit"),
    path("billing/", views.settings_billing, name="settings_billing"),
]
