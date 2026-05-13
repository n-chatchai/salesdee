from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz/", views.healthz, name="healthz"),
    path("search/", views.search, name="search"),
    path("notifications/", views.notifications, name="notifications"),
]
