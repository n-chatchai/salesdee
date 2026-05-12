"""Base settings shared by all environments. Env-specific overrides live in dev.py / prod.py."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# Read .env if present (dev). In prod, env vars come from the environment.
env_file = BASE_DIR / ".env"
if env_file.exists():
    env.read_env(str(env_file))

# --- Core ---------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
SITE_BASE_URL = env("SITE_BASE_URL", default="http://localhost:8000")

# --- Applications -------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "django_htmx",
    # Background tasks use Django 6's built-in `django.tasks` framework. To run a durable
    # DB-backed queue, add the database backend app here (e.g. "django.tasks.backends.database")
    # and configure TASKS below — verify the exact module path against the Django 6.0 docs first.
]

LOCAL_APPS = [
    "apps.core",
    "apps.tenants",
    "apps.accounts",
    "apps.crm",
    "apps.catalog",
    "apps.quotes",
    "apps.billing",  # phase 2 — stub for now
    "apps.accounting",  # phase 3 — stub for now
    "apps.integrations",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# --- Middleware ---------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",  # Django 6 built-in CSP
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    # Resolves & activates the current tenant; sets the Postgres session var used by RLS.
    "apps.core.middleware.CurrentTenantMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csp",  # exposes the CSP nonce
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.current_tenant",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database -----------------------------------------------------------------
DATABASES = {
    "default": env.db(
        "DATABASE_URL", default="postgres://quotation:quotation@localhost:5432/quotation"
    ),
}
# DEFAULT_AUTO_FIELD is BigAutoField by default in Django 6.

# --- Auth ---------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "accounts:login"

# --- Background tasks (django.tasks, built into Django 6) ---------------------
# Left unset for now -> uses Django's default backend. When ready for a durable queue,
# add the DB backend app to INSTALLED_APPS and set:
#   TASKS = {"default": {"BACKEND": "django.tasks.backends.database.DatabaseBackend"}}
# then run migrations and `python manage.py db_worker`. (Confirm names against Django 6.0 docs.)
# A Celery/RQ backend can be swapped here later without changing any `@task` call sites.

# --- Cache --------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/0"),
    }
}

# --- i18n / tz (Thai-only for MVP) -------------------------------------------
LANGUAGE_CODE = "th-th"
LANGUAGES = [("th", "ไทย")]
USE_I18N = True
TIME_ZONE = "Asia/Bangkok"
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]
# Documents default to Buddhist Era (พ.ศ.); helpers in apps/core/utils/thai_dates.py.
DOCUMENT_ERA = "BE"  # "BE" (พ.ศ.) | "CE" (ค.ศ.)

# --- Multi-tenancy ------------------------------------------------------------
# When True, the current-tenant context also sets a Postgres session variable
# (app.current_tenant_id) used by Row-Level Security policies. Enable once the
# RLS migration that creates those policies has been applied.
RLS_ENABLED = env.bool("RLS_ENABLED", default=False)
# Dev convenience: fall back to this tenant slug when no authenticated user.
DEV_DEFAULT_TENANT_SLUG = env("DEV_DEFAULT_TENANT_SLUG", default="")
# Base domain for built-in tenant subdomains: <tenant.slug>.<APP_DOMAIN>.
APP_DOMAIN = env("APP_DOMAIN", default="localhost")
# Hostnames that are the platform itself (marketing / app dashboard, not a tenant).
# A request to one of these does NOT resolve a tenant from the host.
PLATFORM_HOSTS = env.list(
    "PLATFORM_HOSTS",
    default=["localhost", "127.0.0.1", APP_DOMAIN, f"app.{APP_DOMAIN}", f"www.{APP_DOMAIN}"],
)
# NOTE: with custom domains, ALLOWED_HOSTS can't be a fixed list in production. Either set
# ALLOWED_HOSTS=["*"] and rely on CurrentTenantMiddleware to reject hosts that don't map to a
# known platform host or verified TenantDomain, or front the app with a proxy that does it.
# DNS (CNAME) + on-demand TLS for tenant custom domains is a deployment concern.

# --- Static / media -----------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# --- Email --------------------------------------------------------------------
vars().update(env.email_url("EMAIL_URL", default="consolemail://"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@localhost")

# --- Security headers (CSP, Django 6 built-in) --------------------------------
# Plain-string values are used to avoid depending on the exact `django.utils.csp` API.
# `'nonce-{nonce}'` is replaced per-response by the CSP middleware; use `{{ csp_nonce }}`
# in templates for any inline <script>/<style>. Tighten this (and the CDN <script src> hosts
# in templates/base.html) before production. CSP is disabled in dev.py.
SECURE_CSP: dict[str, list[str]] | None = {
    "default-src": ["'self'"],
    "script-src": [
        "'self'",
        "'nonce-{nonce}'",
        "https://cdn.tailwindcss.com",
        "https://unpkg.com",
        "https://cdn.jsdelivr.net",
    ],
    "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
    "img-src": ["'self'", "data:"],
    "font-src": ["'self'", "https://fonts.gstatic.com"],
    "connect-src": ["'self'"],
    "frame-ancestors": ["'none'"],
    "base-uri": ["'self'"],
}

# --- Misc ---------------------------------------------------------------------
DEFAULT_CHARSET = "utf-8"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"

# Money / rounding conventions (see CLAUDE.md §4).
MONEY_DECIMAL_PLACES = 4
RATE_DECIMAL_PLACES = 6
DISPLAY_DECIMAL_PLACES = 2
DEFAULT_VAT_RATE = "0.07"  # string -> Decimal at use site
