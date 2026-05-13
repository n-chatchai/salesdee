"""Production settings. All secrets/hosts come from the environment."""

from .base import *  # noqa: F403

DEBUG = False

# Required env vars in prod (fail loudly if missing).
SECRET_KEY = env("SECRET_KEY")  # noqa: F405
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")  # noqa: F405

# Background tasks: production runs an actual qcluster worker process, so async_task
# must enqueue (not run inline). Base sets sync=True for dev/tests.
Q_CLUSTER = {**Q_CLUSTER, "sync": False}  # noqa: F405

# HTTPS / cookies
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Static files served via WhiteNoise or a CDN — wire up when deploying.
# STORAGES["staticfiles"]["BACKEND"] = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Logging: structured to stdout (container-friendly).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
