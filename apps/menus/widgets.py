from apps.core.widgets import Widget
from apps.core.widgets import register as register_widget
from apps.organizations.permissions import can, module_enabled

from .models import Menu


def _context(request):
    menus = Menu.objects.for_org(request.organization)
    return {"menus_latest": menus[:3]}


def register() -> None:
    register_widget(Widget("menus", "menus/widgets/overview.html", _context, order=27,
                           visible=lambda r: module_enabled(r, "menus")
                           and can(r, "content.view")))
