from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.catalog import views as catalog_views
from apps.quotes import views as quote_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("crm/", include("apps.crm.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("quotes/", include("apps.quotes.urls")),
    path("billing/", include("apps.billing.urls")),
    path("integrations/", include("apps.integrations.urls")),
    path("settings/", include("apps.tenants.urls")),
    path("audit/", include("apps.audit.urls")),
    # Public, login-free quotation share links (tenant resolved from the token).
    path("q/<str:token>/", quote_views.public_quotation, name="public_quotation"),
    path(
        "q/<str:token>/respond/",
        quote_views.public_quotation_respond,
        name="public_quotation_respond",
    ),
    path("q/<str:token>/pdf/", quote_views.public_quotation_pdf, name="public_quotation_pdf"),
    # Public, login-free catalog / showroom (tenant resolved from the URL slug).
    path("c/<slug:tenant_slug>/home/", catalog_views.public_home, name="public_home"),
    path("c/<slug:tenant_slug>/", catalog_views.public_catalog, name="public_catalog"),
    path(
        "c/<slug:tenant_slug>/match/",
        catalog_views.public_catalog_match,
        name="public_catalog_match",
    ),
    path("c/<slug:tenant_slug>/p/<int:pk>/", catalog_views.public_product, name="public_product"),
    path(
        "c/<slug:tenant_slug>/request/",
        catalog_views.public_quote_request,
        name="public_quote_request",
    ),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    try:
        import debug_toolbar  # noqa: F401

        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
    except ImportError:
        pass
