from django.utils.translation import gettext_lazy as _

from apps.core.navigation import NavItem
from apps.core.navigation import register as register_item
from apps.organizations.permissions import can


def register() -> None:
    register_item(NavItem("billing", _("Plan & billing"), "billing", "card", order=950,
                          section="workspace", visible=lambda r: can(r, "billing.view")))
