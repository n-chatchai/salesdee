"""Local development settings."""

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE.insert(  # noqa: F405
    MIDDLEWARE.index("django.middleware.common.CommonMiddleware") + 1,  # noqa: F405
    "debug_toolbar.middleware.DebugToolbarMiddleware",
)
INTERNAL_IPS = ["127.0.0.1"]

# Relax CSP a bit in dev so the debug toolbar / live reload work.
SECURE_CSP = None  # disable CSP enforcement locally; prod sets it.

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
