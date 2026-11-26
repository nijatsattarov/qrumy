from django.utils.translation import gettext_lazy as _

from apps.core.navigation import NavItem
from apps.core.navigation import register as register_item
from apps.core.qr_products import ProductTile
from apps.core.qr_products import register as register_tile
from apps.organizations.permissions import can, module_enabled


def register() -> None:
    register_item(NavItem("card", _("Qrumy Card"), "card_list", "user", order=25,
                          visible=lambda r: module_enabled(r, "cards")
                          and can(r, "content.view")))
    register_tile(ProductTile("cards", _("Qrumy Card"),
                              _("Digital business card with contacts and social media"),
                              "user", "card_create",
                              visible=lambda r: module_enabled(r, "cards")
                              and can(r, "content.create"), order=2))
