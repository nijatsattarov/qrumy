from django.utils.translation import gettext_lazy as _

from apps.core.navigation import NavItem
from apps.core.navigation import register as register_item

from .permissions import can


def register() -> None:
    register_item(NavItem("dashboard", _("Overview"), "dashboard", "home", order=0))
    register_item(NavItem("team", _("Team"), "team", "users", order=900, section="workspace",
                          visible=lambda r: can(r, "team.view")))
    register_item(NavItem("organization_settings", _("Settings"), "organization_settings",
                          "settings", order=990, section="workspace",
                          visible=lambda r: can(r, "org.settings.edit")))
