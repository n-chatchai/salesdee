from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("crm/", include("apps.crm.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("quotes/", include("apps.quotes.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    try:
        import debug_toolbar  # noqa: F401

        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
    except ImportError:
        pass
