from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MenusConfig(AppConfig):
    name = "apps.menus"
    label = "menus"
    verbose_name = _("Digital Menu")

    def ready(self) -> None:
        from . import navigation, qr_type, widgets

        navigation.register()
        widgets.register()
        qr_type.register()
