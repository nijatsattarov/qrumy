from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AssetsConfig(AppConfig):
    name = "apps.assets"
    label = "assets"
    verbose_name = _("Asset Management")

    def ready(self) -> None:
        from . import navigation, qr_type, widgets

        navigation.register()
        widgets.register()
        qr_type.register()
