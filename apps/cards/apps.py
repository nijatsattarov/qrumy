from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CardsConfig(AppConfig):
    name = "apps.cards"
    label = "cards"
    verbose_name = _("Qrumy Card")

    def ready(self) -> None:
        from . import navigation, qr_type, widgets

        navigation.register()
        widgets.register()
        qr_type.register()
