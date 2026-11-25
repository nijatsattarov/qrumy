from .base import *  # noqa

DEBUG = env.bool("DEBUG", default=True)
QRUMY_ADMIN_REQUIRE_MFA = env.bool("QRUMY_ADMIN_REQUIRE_MFA", default=False)
STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
