from django.utils.translation import gettext_lazy as _

from apps.core.navigation import NavItem
from apps.core.navigation import register as register_item
from apps.organizations.permissions import can, module_enabled


def register() -> None:
    register_item(NavItem("card", _("Qrumy Card"), "card_list", "user", order=25,
                          visible=lambda r: module_enabled(r, "cards")
                          and can(r, "content.view")))
