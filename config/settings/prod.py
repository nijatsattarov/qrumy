from .base import *  # noqa

DEBUG = False
QRUMY_TRUSTED_PROXY_COUNT = env.int("QRUMY_TRUSTED_PROXY_COUNT", default=1)
SECRET_KEY = env("SECRET_KEY")  # required, no default
# Rotate keys without logging everyone out: put the old key here for a while.
SECRET_KEY_FALLBACKS = env.list("SECRET_KEY_FALLBACKS", default=[])
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# HSTS preload is a long-term commitment (hard to undo); enable only after the domain is
# stable on HTTPS everywhere, then submit it at hstspreload.org.
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
if not SECURE_HSTS_PRELOAD:
    SILENCED_SYSTEM_CHECKS = ["security.W021"]
# Public links (QR codes, cards, emails) are built from SITE_URL: never ship localhost.
if not SITE_URL.startswith("https://") or any(
        h in SITE_URL for h in ("localhost", "127.0.0.1", "0.0.0.0")):  # noqa: S104
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("SITE_URL must be the public https:// address, e.g. "
                               "https://qrumy.com")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[SITE_URL])
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=env("SENTRY_ENVIRONMENT", default="production"),
        integrations=[DjangoIntegration(), CeleryIntegration()],
        # Privacy: no user details, request bodies, SQL parameters or local variables
        # (they can contain emails, survey answers or lead data) in error reports.
        data_collection={"user_info": False, "http_bodies": [], "database_query_data": False,
                         "stack_frame_variables": False},
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
    )
QRUMY_SERVE_FILES_WITH_X_ACCEL = env.bool("QRUMY_SERVE_FILES_WITH_X_ACCEL", default=True)
