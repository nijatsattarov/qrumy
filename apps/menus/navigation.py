from django.utils.translation import gettext_lazy as _

from apps.core.navigation import NavItem
from apps.core.navigation import register as register_item
from apps.core.qr_products import ProductTile
from apps.core.qr_products import register as register_tile
from apps.organizations.permissions import can, module_enabled


def register() -> None:
    register_item(NavItem("menu", _("Digital Menu"), "menu_list", "menu-book", order=27,
                          visible=lambda r: module_enabled(r, "menus")
                          and can(r, "content.view")))
    register_tile(ProductTile("menus", _("Digital Menu"),
                              _("Interactive menu with photos, prices and categories"),
                              "menu-book", "menu_create",
                              visible=lambda r: module_enabled(r, "menus")
                              and can(r, "content.create"), order=1))
