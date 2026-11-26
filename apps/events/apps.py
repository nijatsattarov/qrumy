from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class EventsConfig(AppConfig):
    name = "apps.events"
    label = "events"
    verbose_name = _("Event Lead Capture")

    def ready(self) -> None:
        from . import navigation, qr_type, widgets

        navigation.register()
        widgets.register()
        qr_type.register()
