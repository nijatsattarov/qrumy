from .base import *  # noqa

DEBUG = False
SECRET_KEY = "test-secret-key"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
SESSION_ENGINE = "django.contrib.sessions.backends.db"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
MEDIA_ROOT = BASE_DIR / ".pytest_media"
QRUMY_SCAN_BUFFER = "sync"
QRUMY_QR_BASE_URL = "https://qrumy.com/q/"
QRUMY_ADMIN_PATH = "qadmin/"
QRUMY_ADMIN_REQUIRE_MFA = True
ACCOUNT_RATE_LIMITS = False
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m]
