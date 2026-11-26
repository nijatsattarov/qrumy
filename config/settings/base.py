"""Base settings shared by every environment."""

from pathlib import Path

import environ
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
SITE_URL = env("SITE_URL", default="http://localhost:8000").rstrip("/")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
QRUMY_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.audit_logs",
    "apps.notifications",
    "apps.organizations",
    "apps.subscriptions",
    "apps.billing",
    "apps.analytics",
    "apps.qr_management",
    "apps.surveys",
    "apps.assets",
    "apps.marketing",
]

INSTALLED_APPS = [
    # Unfold must precede django.contrib.admin
    "unfold",
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
    "django.forms",
    # Third-party
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.mfa",
    "rest_framework",
    "django_htmx",
    "template_partials",
    "django_countries",
    "django_celery_beat",
    "csp",
    *QRUMY_APPS,
]

MIDDLEWARE = [
    "apps.core.middleware.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.UserLanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "csp.middleware.CSPMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "apps.core.middleware.AdminAccessMiddleware",
    "apps.organizations.middleware.OrganizationMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "apps.core.context_processors.qrumy",
                "apps.notifications.context_processors.notifications",
                "apps.organizations.context_processors.organizations",
            ],
        },
    }
]

# ---------------------------------------------------------------------------
# Database / cache
# ---------------------------------------------------------------------------
DATABASES = {"default": env.db("DATABASE_URL", default="postgres://postgres@127.0.0.1:5432/qrumy")}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "qrumy",
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# ---------------------------------------------------------------------------
# Auth (django-allauth)
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "app_home"
ACCOUNT_LOGOUT_REDIRECT_URL = "home"

ACCOUNT_ADAPTER = "apps.accounts.adapters.AccountAdapter"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_SIGNUP_FORM_CLASS = "apps.accounts.forms.SignupExtraForm"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_CONFIRM_EMAIL_ON_GET = False
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGIN_ON_PASSWORD_RESET = False
ACCOUNT_SESSION_REMEMBER = None  # user chooses via "Remember me"
ACCOUNT_EMAIL_SUBJECT_PREFIX = "Qrumy — "
ACCOUNT_PREVENT_ENUMERATION = True
ACCOUNT_RATE_LIMITS = {
    "login_failed": "10/m/ip,5/5m/key",
    "signup": "20/h/ip",
    "confirm_email": "1/3m/key",
    "reset_password": "20/m/ip,5/m/key",
}
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_TOTP_ISSUER = "Qrumy"

GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")
SOCIALACCOUNT_PROVIDERS = {}
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    SOCIALACCOUNT_PROVIDERS["google"] = {
        "APPS": [{"client_id": GOOGLE_CLIENT_ID, "secret": GOOGLE_CLIENT_SECRET, "key": ""}],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# ---------------------------------------------------------------------------
# i18n — English (default) + Azerbaijani
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en"
LANGUAGES = [("en", _("English")), ("az", _("Azerbaijani"))]
# locale/ is ours (makemessages writes there); locale_vendor/ holds Azerbaijani
# translations for third-party packages that ship none (django-unfold).
LOCALE_PATHS = [BASE_DIR / "locale", BASE_DIR / "locale_vendor"]
# The super-admin is always shown in Azerbaijani.
QRUMY_ADMIN_LANGUAGE = env("QRUMY_ADMIN_LANGUAGE", default="az")
USE_I18N = True
USE_TZ = True
TIME_ZONE = "UTC"
QRUMY_DEFAULT_TIMEZONE = "Asia/Baku"

# ---------------------------------------------------------------------------
# Static & media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Files that must never be served directly by the web server (served via views).
    "private": {"BACKEND": "django.core.files.storage.FileSystemStorage",
                "OPTIONS": {"location": str(MEDIA_ROOT / "private"), "base_url": None}},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
RESEND_API_KEY = env("RESEND_API_KEY", default="")
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default=(
        "anymail.backends.resend.EmailBackend"
        if RESEND_API_KEY
        else "django.core.mail.backends.console.EmailBackend"
    ),
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Qrumy <no-reply@qrumy.com>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
ANYMAIL = {
    **env.dict("ANYMAIL", default={}),
    **({"RESEND_API_KEY": RESEND_API_KEY} if RESEND_API_KEY else {}),
}
EMAIL_TIMEOUT = 15

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = None
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TIMEZONE = "UTC"

# ---------------------------------------------------------------------------
# REST framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"user": "600/min"},
}

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # HTMX reads the token from the meta tag, not the cookie
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
RATELIMIT_VIEW = "apps.core.views.ratelimited"

QRUMY_ADMIN_PATH = env("QRUMY_ADMIN_PATH", default="qadmin/")
QRUMY_ADMIN_REQUIRE_MFA = env.bool("QRUMY_ADMIN_REQUIRE_MFA", default=True)

CONTENT_SECURITY_POLICY = {
    # Unfold (Django Admin theme) relies on inline scripts; the admin is staff-only.
    "EXCLUDE_URL_PREFIXES": ["/" + QRUMY_ADMIN_PATH],
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'"],
        "img-src": ["'self'", "data:", "blob:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "form-action": ["'self'", "https://accounts.google.com"],
        "base-uri": ["'self'"],
        "object-src": ["'none'"],
    },
}

# ---------------------------------------------------------------------------
# Qrumy product settings
# ---------------------------------------------------------------------------
# Plan automatically assigned to new organizations (free beta).
QRUMY_DEFAULT_PLAN = env("QRUMY_DEFAULT_PLAN", default="beta")
QRUMY_INVITATION_TTL_DAYS = 7
# Product modules that are implemented and can be shown in navigation / marketing.
# A module is listed here only once it actually works (see docs/CHECKLIST.md).
QRUMY_AVAILABLE_MODULES: list[str] = ["qr", "surveys", "assets"]

# --- QR Management / analytics ---
# Base of dynamic QR links. Changing it later only affects codes created afterwards.
QRUMY_QR_BASE_URL = env("QRUMY_QR_BASE_URL", default=SITE_URL + "/q/")
# "redis" buffers scans and processes them in Celery; "sync" writes immediately (tests/dev).
QRUMY_SCAN_BUFFER = env("QRUMY_SCAN_BUFFER", default="redis")
QRUMY_SCAN_RETENTION_DAYS = env.int("QRUMY_SCAN_RETENTION_DAYS", default=180)
QRUMY_GEOIP_CITY_DB = env("QRUMY_GEOIP_CITY_DB", default=str(BASE_DIR / "var/GeoLite2-City.mmdb"))
# Trust a CDN country header (e.g. "HTTP_CF_IPCOUNTRY") when no GeoIP database is present.
QRUMY_COUNTRY_HEADER = env("QRUMY_COUNTRY_HEADER", default="")
QRUMY_SAFE_BROWSING_KEY = env("QRUMY_SAFE_BROWSING_KEY", default="")
QRUMY_BLOCKED_DOMAINS = env.list("QRUMY_BLOCKED_DOMAINS", default=[])
QRUMY_SERVE_FILES_WITH_X_ACCEL = env.bool("QRUMY_SERVE_FILES_WITH_X_ACCEL", default=False)

CELERY_BEAT_SCHEDULE = {
    "analytics-process-scan-buffer": {
        "task": "apps.analytics.tasks.process_scan_buffer", "schedule": 15.0},
    "analytics-purge-old-scans": {
        "task": "apps.analytics.tasks.purge_old_scans", "schedule": 60 * 60 * 6},
}

# ---------------------------------------------------------------------------
# Django Admin theme (Unfold)
# ---------------------------------------------------------------------------
UNFOLD = {
    "SITE_TITLE": "Qrumy Admin",
    "SITE_HEADER": "Qrumy",
    "SITE_SYMBOL": "qr_code_2",
    "SHOW_HISTORY": True,
    "DASHBOARD_CALLBACK": "apps.core.admin_dashboard.dashboard_callback",
    "COLORS": {
        "primary": {
            "50": "238 242 255", "100": "224 231 255", "200": "199 210 254",
            "300": "165 180 252", "400": "120 146 255", "500": "79 124 255",
            "600": "59 98 230", "700": "29 46 91", "800": "22 35 72", "900": "16 27 58",
            "950": "10 17 38",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}

FORM_RENDERER = "apps.core.forms.QrumyFormRenderer"
# Number of trusted reverse proxies in front of the app (Nginx = 1 in production).
QRUMY_TRUSTED_PROXY_COUNT = env.int("QRUMY_TRUSTED_PROXY_COUNT", default=0)
# django-ratelimit: use the real client IP (Nginx sets X-Forwarded-For).
RATELIMIT_IP_META_KEY = "apps.core.utils.client_ip"
