from apps.core.widgets import Widget
from apps.core.widgets import register as register_widget
from apps.organizations.permissions import can, module_enabled

from . import stats
from .models import FaultReport


def _context(request):
    org = request.organization
    return {**stats.overview(org),
            "latest_faults": FaultReport.objects.for_org(org).filter(
                status__in=FaultReport.OPEN_STATUSES).select_related("asset")[:4]}


def register() -> None:
    register_widget(Widget("assets", "assets/widgets/overview.html", _context, order=30,
                           visible=lambda r: module_enabled(r, "assets")
                           and can(r, "content.view")))
