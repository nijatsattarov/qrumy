from django.utils.translation import gettext_lazy as _

from apps.core.navigation import NavItem
from apps.core.navigation import register as register_item
from apps.organizations.permissions import can, module_enabled


def register() -> None:
    register_item(NavItem("survey", _("Surveys"), "survey_list", "message", order=20,
                          visible=lambda r: module_enabled(r, "surveys")
                          and can(r, "content.view")))
