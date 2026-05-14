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
    "django_q",  # background queue + scheduler (Redis-backed); see Q_CLUSTER below
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
    "apps.audit",
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

# --- Redis URLs ---------------------------------------------------------------
# Queue and cache go to SEPARATE logical DB indexes on the same Redis instance so a
# cache `FLUSHDB` never wipes queued/scheduled tasks. `REDIS_URL` is the fallback; the
# more-specific vars override.
_REDIS_DEFAULT = env("REDIS_URL", default="redis://localhost:6379/0")
Q_REDIS_URL = env("Q_REDIS_URL", default=_REDIS_DEFAULT)
CACHE_REDIS_URL = env("CACHE_REDIS_URL", default=_REDIS_DEFAULT)

# --- Background tasks (django-q2 — Redis-backed queue + scheduler) -----------
# `apps/core/tasks.py::task` decorator wraps a function in a `.enqueue()`-having object
# that `async_task`s it onto django-q's Redis broker; the `qcluster` process drains the
# queue + runs scheduled jobs (the `Schedule` admin/model). In dev/tests `sync=True`
# runs every `async_task` inline so tests assert post-POST side effects unchanged.
Q_CLUSTER = {
    "name": "salesdee",
    "workers": env.int("Q_WORKERS", default=2),
    "recycle": 200,
    "timeout": 120,
    "retry": 180,
    "queue_limit": 50,
    "bulk": 10,
    "redis": Q_REDIS_URL,
    # Run tasks synchronously by default (dev + tests). Production overrides → False.
    "sync": env.bool("Q_SYNC", default=True),
    "log_level": "INFO",
}

# --- Cache --------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": CACHE_REDIS_URL,
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

# Media storage: filesystem by default; flip to Cloudflare R2 (S3-compatible) when USE_R2=True.
# R2 is private — django-storages signs every GET URL (querystring_auth) with the lifetime
# configured here, so leaked URLs auto-expire. Static files stay on disk + are served by Nginx
# (already cheap + Cloudflare-cached); no need to host them on R2.
USE_R2 = env.bool("USE_R2", default=False)
if USE_R2:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": env("R2_BUCKET"),
                "endpoint_url": env("R2_ENDPOINT_URL"),
                "access_key": env("R2_ACCESS_KEY_ID"),
                "secret_key": env("R2_SECRET_ACCESS_KEY"),
                "region_name": env("R2_REGION", default="auto"),
                "addressing_style": "virtual",
                "signature_version": "s3v4",
                "default_acl": None,  # R2 doesn't honour S3 ACLs
                "querystring_auth": True,  # presign every URL
                "querystring_expire": env.int("R2_URL_TTL_SECONDS", default=3600),
                "file_overwrite": False,
            },
        },
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

# --- Email --------------------------------------------------------------------
vars().update(env.email_url("EMAIL_URL", default="consolemail://"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@localhost")

# --- AI (Anthropic / Claude) — optional; AI features are disabled when the key is blank -------
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", default="claude-sonnet-4-6")

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
