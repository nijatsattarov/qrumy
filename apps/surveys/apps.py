from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SurveysConfig(AppConfig):
    name = "apps.surveys"
    label = "surveys"
    verbose_name = _("Surveys & Feedback")

    def ready(self) -> None:
        from . import navigation, qr_type, widgets

        navigation.register()
        widgets.register()
        qr_type.register()
