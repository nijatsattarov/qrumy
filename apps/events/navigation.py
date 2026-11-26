from django.utils.translation import gettext_lazy as _

from apps.core.navigation import NavItem
from apps.core.navigation import register as register_item
from apps.organizations.permissions import can, module_enabled


def register() -> None:
    register_item(NavItem("event", _("Events & leads"), "event_list", "calendar", order=35,
                          visible=lambda r: module_enabled(r, "events")
                          and can(r, "content.view")))
