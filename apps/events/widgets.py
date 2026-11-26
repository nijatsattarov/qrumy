from apps.core.widgets import Widget
from apps.core.widgets import register as register_widget
from apps.organizations.permissions import can, module_enabled

from .models import Event, Lead


def _context(request):
    org = request.organization
    return {"events_latest": Event.objects.for_org(org)[:3],
            "leads_new": Lead.objects.for_org(org).filter(stage="new").count()}


def register() -> None:
    register_widget(Widget("events", "events/widgets/overview.html", _context, order=35,
                           visible=lambda r: module_enabled(r, "events")
                           and can(r, "content.view")))
