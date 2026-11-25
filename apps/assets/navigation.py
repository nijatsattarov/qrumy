from django.utils.translation import gettext_lazy as _

from apps.core.navigation import NavItem
from apps.core.navigation import register as register_item
from apps.organizations.permissions import can, module_enabled


def register() -> None:
    register_item(NavItem("asset", _("Assets"), "asset_list", "box", order=30,
                          visible=lambda r: module_enabled(r, "assets")
                          and can(r, "content.view")))
