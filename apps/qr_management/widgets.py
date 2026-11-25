from apps.analytics import reports
from apps.core.widgets import Widget
from apps.core.widgets import register as register_widget
from apps.organizations.permissions import can, module_enabled

from .models import QRCode


def _context(request):
    org = request.organization
    period = reports.Period.last_days(30)
    codes = QRCode.objects.for_org(org).live()
    return {
        "qr_count": codes.count(),
        "dynamic_count": codes.filter(mode="dynamic").count(),
        "scans_30d": reports.totals(org, period)["scans"],
        "top_codes": reports.top_codes(org, period, limit=4),
    }


def register() -> None:
    register_widget(Widget("qr", "qr_management/widgets/overview.html", _context, order=10,
                           visible=lambda r: module_enabled(r, "qr") and can(r, "content.view")))
