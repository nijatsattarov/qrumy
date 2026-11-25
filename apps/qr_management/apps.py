from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class QrManagementConfig(AppConfig):
    name = "apps.qr_management"
    label = "qr_management"
    verbose_name = _("QR Management")

    def ready(self) -> None:
        from . import navigation, widgets

        navigation.register()
        widgets.register()
