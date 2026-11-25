from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SubscriptionsConfig(AppConfig):
    name = "apps.subscriptions"
    label = "subscriptions"
    verbose_name = _("Subscriptions")

    def ready(self) -> None:
        from . import signals  # noqa: F401
        from .quota_backend import register

        register()

