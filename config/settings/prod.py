from .base import *  # noqa

DEBUG = False
QRUMY_TRUSTED_PROXY_COUNT = env.int("QRUMY_TRUSTED_PROXY_COUNT", default=1)
SECRET_KEY = env("SECRET_KEY")  # required, no default
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[SITE_URL])
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:  # optional dependency, installed only where used
    import sentry_sdk

    sentry_sdk.init(dsn=SENTRY_DSN, send_default_pii=False, traces_sample_rate=0.0)
QRUMY_SERVE_FILES_WITH_X_ACCEL = env.bool("QRUMY_SERVE_FILES_WITH_X_ACCEL", default=True)
