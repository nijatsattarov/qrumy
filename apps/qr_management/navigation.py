from django.utils.translation import gettext_lazy as _

from apps.core.navigation import NavItem
from apps.core.navigation import register as register_item
from apps.organizations.permissions import can, module_enabled


def register() -> None:
    register_item(NavItem("qr", _("QR Codes"), "qr_list", "qr", order=10,
                          visible=lambda r: module_enabled(r, "qr") and can(r, "content.view")))
    register_item(NavItem("analytics", _("Analytics"), "analytics_overview", "chart", order=80,
                          visible=lambda r: module_enabled(r, "qr") and can(r, "analytics.view")))
